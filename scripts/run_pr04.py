#!/usr/bin/env python3
"""Record the PR04 runtime parameter experiment using installed ROS 2.

Source ROS and the workspace before running. Qt runs offscreen so this can be
repeated without a graphical desktop. Use an otherwise empty ROS domain.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "pr04"
DOMAIN = int(os.environ.get("ROS_DOMAIN_ID", "17"))
TWIST = "{linear: {x: 1.0}, angular: {z: 0.5}}"
COMMANDS: list[dict] = []
PROCESSES: list[subprocess.Popen] = []


def environment() -> dict[str, str]:
    env = os.environ.copy()
    env["ROS_DOMAIN_ID"] = str(DOMAIN)
    env["ROS_LOG_DIR"] = "/tmp/ros-pr04-logs"
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONUNBUFFERED"] = "1"
    Path(env["ROS_LOG_DIR"]).mkdir(parents=True, exist_ok=True)
    return env


def run(args: list[str], filename: str, timeout: int = 30) -> str:
    result = subprocess.run(
        args, cwd=ROOT, env=environment(), capture_output=True, text=True,
        timeout=timeout,
    )
    output = result.stdout + result.stderr
    (EVIDENCE / filename).write_text(output)
    COMMANDS.append({"command": shlex.join(args), "output": filename,
                     "exit_code": result.returncode})
    if result.returncode:
        raise RuntimeError(f"{shlex.join(args)} failed ({result.returncode}): {output}")
    return output


def start(args: list[str], filename: str) -> subprocess.Popen:
    output = (EVIDENCE / filename).open("w")
    process = subprocess.Popen(
        args, cwd=ROOT, env=environment(), stdin=subprocess.DEVNULL,
        stdout=output, stderr=subprocess.STDOUT, start_new_session=True,
    )
    output.close()
    PROCESSES.append(process)
    COMMANDS.append({"command": shlex.join(args), "output": filename,
                     "pid": process.pid})
    return process


def stop(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    # ros2 run/launch forwards SIGINT; signal only the wrapper once.
    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)


def nodes(filename: str) -> set[str]:
    output = run(["ros2", "node", "list", "--no-daemon", "--spin-time", "2"], filename)
    return {line.strip() for line in output.splitlines() if line.startswith("/")}


def wait_for_node(process: subprocess.Popen, expected: set[str], filename: str) -> None:
    for _ in range(8):
        if process.poll() is not None:
            raise RuntimeError("launch exited early; inspect its log")
        if nodes(filename) == expected:
            return
        time.sleep(0.5)
    raise RuntimeError(f"Expected nodes {expected} did not appear")


def pose(filename: str, pose_type: str) -> dict[str, float]:
    output = run(["timeout", "8s", "ros2", "topic", "echo", "/turtle1/pose",
                  pose_type, "--once", "--no-daemon"], filename, timeout=12)
    fields = {name: float(value) for name, value in re.findall(
        r"^(x|y|theta|linear_velocity|angular_velocity):\s*([-+0-9.eE]+)$",
        output, re.M,
    )}
    if not {"x", "y", "theta"} <= fields.keys():
        raise RuntimeError(f"Could not parse pose: {output}")
    return fields


def distance(a: dict[str, float], b: dict[str, float]) -> float:
    return math.hypot(b["x"] - a["x"], b["y"] - a["y"])


def measure(filename: str, expected: float) -> float:
    process = start(["ros2", "topic", "hz", "/turtle1/cmd_vel"], filename)
    try:
        time.sleep(15)
    finally:
        stop(process)
    rates = re.findall(r"average rate:\s*([0-9.]+)", (EVIDENCE / filename).read_text())
    if not rates or abs(float(rates[-1]) - expected) > 0.5:
        raise RuntimeError(f"Expected {expected} Hz; see {filename}")
    return float(rates[-1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--defect-checkout', type=Path,
                        help='Separate checkout with frequency validation disabled')
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    measurements = {"domain": DOMAIN}
    try:
        if nodes("nodes-initial.txt"):
            raise RuntimeError(f"ROS domain {DOMAIN} contains other nodes")
        simulator = start(["ros2", "launch", "turtle_bringup", "sim.launch.py"], "simulator.txt")
        wait_for_node(simulator, {"/turtlesim"}, "nodes-simulator.txt")
        pose_type = run(["ros2", "topic", "type", "/turtle1/pose",
                         "--no-daemon", "--spin-time", "2"], "pose-type.txt").strip()
        patrol = start(["ros2", "run", "patrol", "patrol", "--ros-args",
                        "-r", "cmd_vel:=/turtle1/cmd_vel"], "patrol-fixed.txt")
        wait_for_node(patrol, {"/turtlesim", "/patrol"}, "nodes-fixed.txt")
        run(["ros2", "param", "dump", "/patrol"], "parameters-initial.txt")
        measurements["initial_hz"] = measure("hz-initial.txt", 10.)
        output = run(["ros2", "param", "set", "/patrol", "publish_hz", "0.0"], "zero-rejected.txt")
        assert "Setting parameter failed" in output
        value = run(["ros2", "param", "get", "/patrol", "publish_hz"], "frequency-after-zero.txt")
        assert "10.0" in value
        measurements["after_zero_hz"] = measure("hz-after-zero.txt", 10.)
        output = run(["ros2", "param", "set", "/patrol", "publish_hz", "5.0"], "set-five.txt")
        assert "successful" in output.lower()
        measurements["changed_hz"] = measure("hz-five.txt", 5.)
        for name, value in (("linear_speed", "0.2"), ("turn_rate", "-0.4")):
            output = run(["ros2", "param", "set", "/patrol", name, value], f"set-{name}.txt")
            assert "successful" in output.lower()
        command = run(["timeout", "8s", "ros2", "topic", "echo", "/turtle1/cmd_vel",
                       "geometry_msgs/msg/Twist", "--once", "--no-daemon"], "command-updated.txt", 12)
        assert "x: 0.2" in command and "z: -0.4" in command
        run(["ros2", "param", "dump", "/patrol"], "parameters-final.txt")
        run(["ros2", "service", "call", "/clear", "std_srvs/srv/Empty", "{}"], "clear-service.txt")
        actions = run(["ros2", "action", "list", "-t"], "actions.txt")
        assert "/turtle1/rotate_absolute" in actions
        stop(patrol)
        assert patrol.returncode == 0, "Patrol did not shut down cleanly"
        time.sleep(1.5)
        stopped = pose("pose-after-stop.txt", pose_type)
        assert stopped['linear_velocity'] == stopped['angular_velocity'] == 0.
        measurements["after_stop"] = stopped
        if args.defect_checkout:
            checkout = args.defect_checkout.resolve()
            source = checkout / 'src/patrol'
            if not (source / 'patrol/parameters.py').is_file():
                raise RuntimeError(f"No defect source in {checkout}")
            code = f"import sys; sys.path.insert(0, {str(source)!r}); from patrol.patrol import main; main()"
            defect = start(["python3", "-c", code, "--ros-args",
                            "-r", "cmd_vel:=/turtle1/cmd_vel"], "patrol-defect.txt")
            wait_for_node(defect, {"/turtlesim", "/patrol"}, "nodes-defect.txt")
            command = ["timeout", "8s", "ros2", "param", "set", "/patrol", "publish_hz", "0.0"]
            result = subprocess.run(command, cwd=ROOT, env=environment(),
                                    capture_output=True, text=True, timeout=12)
            (EVIDENCE / "zero-defect.txt").write_text(result.stdout + result.stderr)
            COMMANDS.append({"command": shlex.join(command), "output": "zero-defect.txt",
                             "exit_code": result.returncode})
            defect.wait(timeout=5)
            log = (EVIDENCE / "patrol-defect.txt").read_text()
            assert "ZeroDivisionError" in log and defect.returncode != 0
            measurements["defect"] = {"process_exit_code": defect.returncode,
                                       "parameter_command_exit_code": result.returncode,
                                       "failure": next(line for line in log.splitlines()
                                                       if line.startswith("ZeroDivisionError:"))}
        stop(simulator)
        assert not nodes("nodes-final.txt")
        (EVIDENCE / "measurements.json").write_text(json.dumps(measurements, indent=2) + "\n")
        print(json.dumps(measurements, indent=2))
    finally:
        for process in reversed(PROCESSES):
            stop(process)
        (EVIDENCE / "commands.json").write_text(json.dumps(COMMANDS, indent=2) + "\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Record the PR03 timer and remapping experiment using installed ROS 2.

Source ROS and the workspace before running. Qt runs offscreen so this can be
repeated without a graphical desktop. Use an otherwise empty ROS domain.
"""

from __future__ import annotations

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
EVIDENCE = ROOT / "evidence" / "pr03"
DOMAIN = int(os.environ.get("ROS_DOMAIN_ID", "17"))
TWIST = "{linear: {x: 1.0}, angular: {z: 0.5}}"
COMMANDS: list[dict] = []
PROCESSES: list[subprocess.Popen] = []


def environment() -> dict[str, str]:
    env = os.environ.copy()
    env["ROS_DOMAIN_ID"] = str(DOMAIN)
    env["ROS_LOG_DIR"] = "/tmp/ros-pr03-logs"
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
    os.killpg(process.pid, signal.SIGINT)
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


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    try:
        if nodes("nodes-initial.txt"):
            raise RuntimeError(f"ROS domain {DOMAIN} contains other nodes")
        launch = start(["ros2", "launch", "turtle_bringup", "sim.launch.py"], "simulator.txt")
        wait_for_node(launch, {"/turtlesim"}, "nodes-simulator.txt")
        pose_type = run(["ros2", "topic", "type", "/turtle1/pose",
                         "--no-daemon", "--spin-time", "2"], "pose-type.txt").strip()
        broken = start(["ros2", "run", "patrol", "patrol"], "patrol-broken.txt")
        wait_for_node(broken, {"/turtlesim", "/patrol"}, "nodes-broken.txt")
        run(["ros2", "node", "info", "/patrol"], "patrol-info.txt")
        wrong_info = run(["ros2", "topic", "info", "/cmd_vel", "--verbose"], "info-broken.txt")
        run(["ros2", "topic", "info", "/turtle1/cmd_vel", "--verbose"], "info-correct-during-broken.txt")
        run(["timeout", "8s", "ros2", "topic", "echo", "/cmd_vel",
             "geometry_msgs/msg/Twist", "--once", "--no-daemon"], "command-broken.txt", 12)
        before = pose("pose-before-broken.txt", pose_type)
        time.sleep(2)
        after = pose("pose-after-broken.txt", pose_type)
        assert "Subscription count: 0" in wrong_info
        assert distance(before, after) < 0.001
        stop(broken)
        fixed = start(["ros2", "run", "patrol", "patrol", "--ros-args",
                       "-r", "cmd_vel:=/turtle1/cmd_vel"], "patrol-fixed.txt")
        wait_for_node(fixed, {"/turtlesim", "/patrol"}, "nodes-fixed.txt")
        fixed_info = run(["ros2", "topic", "info", "/turtle1/cmd_vel", "--verbose"], "info-fixed.txt")
        assert "Publisher count: 1" in fixed_info and "Subscription count: 1" in fixed_info
        fixed_before = pose("pose-before-fixed.txt", pose_type)
        run(["timeout", "8s", "ros2", "topic", "echo", "/turtle1/cmd_vel",
             "geometry_msgs/msg/Twist", "--once", "--no-daemon"], "command-fixed.txt", 12)
        hz = start(["ros2", "topic", "hz", "/turtle1/cmd_vel"], "cmd-hz.txt")
        started = time.monotonic()
        time.sleep(15)
        stop(hz)
        duration = time.monotonic() - started
        rates = re.findall(r"average rate:\s*([0-9.]+)", (EVIDENCE / "cmd-hz.txt").read_text())
        if not rates:
            raise RuntimeError("No frequency measurement")
        fixed_after = pose("pose-after-fixed.txt", pose_type)
        assert distance(fixed_before, fixed_after) > 0.1
        stop(fixed)
        time.sleep(1.5)
        stopped = pose("pose-after-stop.txt", pose_type)
        assert abs(stopped["linear_velocity"]) < 0.001
        assert abs(stopped["angular_velocity"]) < 0.001
        stop(launch)
        assert not nodes("nodes-final.txt")
        measurements = {
            "domain": DOMAIN, "pose_type": pose_type,
            "broken": {"before": before, "after": after, "distance": distance(before, after)},
            "fixed": {"before": fixed_before, "after": fixed_after,
                      "distance": distance(fixed_before, fixed_after)},
            "command_hz": float(rates[-1]), "measurement_seconds": duration,
            "after_stop": stopped, "stop_wait_seconds": 1.5,
        }
        (EVIDENCE / "measurements.json").write_text(json.dumps(measurements, indent=2) + "\n")
        print(json.dumps(measurements, indent=2))
    finally:
        for process in reversed(PROCESSES):
            stop(process)
        (EVIDENCE / "commands.json").write_text(json.dumps(COMMANDS, indent=2) + "\n")


if __name__ == "__main__":
    main()

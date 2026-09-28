#!/usr/bin/env python3
"""Repeat the PR01 domain experiment with real ROS nodes and a terminal PTY.

Run after sourcing ROS. The simulator uses Qt offscreen; no desktop GUI is
controlled. All recorded measurements come from the installed turtlesim.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import pty
import re
import select
import shlex
import signal
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "pr01"
COMMANDS: list[dict] = []
PROCESSES: list[subprocess.Popen] = []
POSE_TYPE = "turtlesim_msgs/msg/Pose"


def environment(domain: int) -> dict[str, str]:
    env = os.environ.copy()
    env["ROS_DOMAIN_ID"] = str(domain)
    env["ROS_LOG_DIR"] = str(LOG_DIR)
    env["PYTHONUNBUFFERED"] = "1"
    return env


def command(args: list[str], domain: int, filename: str, expected: int = 0) -> str:
    started = time.monotonic()
    completed = subprocess.run(
        args, env=environment(domain), cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=25,
    )
    EVIDENCE.joinpath(filename).write_text(completed.stdout)
    EVIDENCE.joinpath(filename + ".exit.txt").write_text(f"exit={completed.returncode}\n")
    COMMANDS.append({
        "domain": domain, "command": shlex.join(args), "output": filename,
        "exit_code": completed.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
    })
    if completed.returncode != expected:
        raise RuntimeError(f"{filename}: expected {expected}, got {completed.returncode}: {completed.stdout}")
    return completed.stdout


def stop(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGINT)
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=3)


class Teleop:
    def __init__(self, domain: int, stage: str):
        self.master, slave = pty.openpty()
        self.output = bytearray()
        self.path = EVIDENCE / f"teleop-{stage}.txt"
        self.process = subprocess.Popen(
            ["ros2", "run", "turtlesim", "turtle_teleop_key"],
            stdin=slave, stdout=slave, stderr=slave,
            env=environment(domain), cwd=ROOT, start_new_session=True,
        )
        os.close(slave)
        PROCESSES.append(self.process)
        COMMANDS.append({
            "domain": domain, "command": "ros2 run turtlesim turtle_teleop_key",
            "output": self.path.name, "input": "real PTY; arrow-up escape sequence",
        })
        time.sleep(1)
        self.drain()
        if self.process.poll() is not None:
            raise RuntimeError(f"teleop failed: {self.output.decode(errors='replace')}")

    def drain(self) -> None:
        while select.select([self.master], [], [], 0)[0]:
            try:
                chunk = os.read(self.master, 65536)
            except OSError:
                break
            if not chunk:
                break
            self.output.extend(chunk)
        self.path.write_text(self.output.decode(errors="replace").replace("\r\n", "\n"))

    def up(self) -> None:
        os.write(self.master, b"\x1b[A")
        time.sleep(2)
        self.drain()

    def close(self) -> None:
        stop(self.process)
        self.drain()
        os.close(self.master)


def pose(filename: str, observer_domain: int = 16) -> dict[str, float]:
    text = command(
        ["timeout", "5s", "ros2", "topic", "echo", "/turtle1/pose", POSE_TYPE,
         "--once", "--no-daemon"], observer_domain, filename,
    )
    fields = {key: float(value) for key, value in re.findall(
        r"^(x|y|theta|linear_velocity|angular_velocity):\s*([-+0-9.eE]+)$", text, re.M,
    )}
    if not {"x", "y", "theta"} <= fields.keys():
        raise RuntimeError(f"Cannot parse actual pose: {text}")
    return fields


def distance(before: dict, after: dict) -> float:
    return math.hypot(after["x"] - before["x"], after["y"] - before["y"])


def nodes(domain: int, filename: str, expected: set[str]) -> None:
    output = command(
        ["ros2", "node", "list", "--no-daemon", "--spin-time", "2"], domain, filename,
    )
    actual = {line.strip() for line in output.splitlines() if line.startswith("/")}
    if actual != expected:
        raise RuntimeError(f"Unexpected nodes in domain {domain}: {actual}, expected {expected}")


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    teleop = None
    simulator_log = None
    success = False
    try:
        print("Checking domains 16 and 17 for interfering nodes", flush=True)
        nodes(16, "nodes-initial-16.txt", set())
        nodes(17, "nodes-initial-17.txt", set())
        simulator_log = EVIDENCE.joinpath("simulator.txt").open("w")
        env = environment(16)
        env["QT_QPA_PLATFORM"] = "offscreen"
        simulator = subprocess.Popen(
            ["ros2", "run", "turtlesim", "turtlesim_node"],
            env=env, cwd=ROOT, stdout=simulator_log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        PROCESSES.append(simulator)
        COMMANDS.append({
            "domain": 16, "command": "QT_QPA_PLATFORM=offscreen ros2 run turtlesim turtlesim_node",
            "output": "simulator.txt",
        })
        time.sleep(2)
        if simulator.poll() is not None:
            raise RuntimeError("Simulator exited; inspect simulator.txt")

        print("Baseline: discovering graph and measuring movement", flush=True)
        teleop = Teleop(16, "before")
        nodes(16, "nodes-before.txt", {"/turtlesim", "/teleop_turtle"})
        command(["ros2", "topic", "list", "-t", "--no-daemon", "--spin-time", "2"], 16, "topics-before.txt")
        command(["ros2", "node", "info", "/turtlesim", "--no-daemon", "--spin-time", "2"], 16, "turtlesim-info.txt")
        command(["ros2", "node", "info", "/teleop_turtle", "--no-daemon", "--spin-time", "2"], 16, "teleop-info.txt")
        actual_type = command(["ros2", "topic", "type", "/turtle1/pose", "--no-daemon", "--spin-time", "2"], 16, "pose-type.txt").strip()
        if actual_type != POSE_TYPE:
            raise RuntimeError(f"Pose type differs from Lyrical: {actual_type}")
        before = pose("pose-before.txt")
        teleop.up()
        moved = pose("pose-after-key-before.txt")
        baseline_distance = distance(before, moved)
        if baseline_distance <= 0.1:
            raise RuntimeError(f"Arrow key did not move turtle: {baseline_distance}")

        print("Measuring pose frequency for 15 seconds", flush=True)
        hz_output = command(
            ["timeout", "--signal=INT", "15s", "ros2", "topic", "hz", "/turtle1/pose"],
            16, "pose-hz.txt", expected=124,
        )
        rates = [float(rate) for rate in re.findall(r"average rate:\s*([0-9.]+)", hz_output)]
        if not rates:
            raise RuntimeError("No frequency measurements were received")
        last_hz = rates[-1]

        teleop.close()
        teleop = None
        print("Broken stage: restarting teleop in domain 17", flush=True)
        teleop = Teleop(17, "broken")
        nodes(17, "nodes-broken.txt", {"/teleop_turtle"})
        command(
            ["timeout", "5s", "ros2", "topic", "echo", "/turtle1/pose", POSE_TYPE,
             "--once", "--no-daemon"], 17, "pose-broken.txt", expected=124,
        )
        before_broken_key = pose("pose-observed-before-broken-key.txt")
        teleop.up()
        after_broken_key = pose("pose-observed-after-broken-key.txt")
        broken_distance = distance(before_broken_key, after_broken_key)
        if broken_distance > 0.001:
            raise RuntimeError(f"Turtle unexpectedly moved across domains: {broken_distance}")
        teleop.close()
        teleop = None

        print("Fixed stage: restarting teleop in domain 16", flush=True)
        teleop = Teleop(16, "fixed")
        nodes(16, "nodes-fixed.txt", {"/turtlesim", "/teleop_turtle"})
        fixed = pose("pose-fixed.txt")
        teleop.up()
        fixed_moved = pose("pose-after-key-fixed.txt")
        fixed_distance = distance(fixed, fixed_moved)
        if fixed_distance <= 0.1:
            raise RuntimeError(f"Restored teleop did not move turtle: {fixed_distance}")

        summary = {
            "experiment_completed": True,
            "execution": "native ROS 2; Qt offscreen simulator; actual arrow-up input through PTY",
            "pose_type": POSE_TYPE,
            "frequency": {"command_duration_seconds": 15, "last_average_hz": last_hz, "samples": rates},
            "baseline": {"domain": 16, "before": before, "after_arrow": moved, "movement_distance": baseline_distance},
            "broken": {"simulator_domain": 16, "teleop_and_observer_domain": 17, "echo_exit": 124,
                       "before_arrow_in_domain16": before_broken_key, "after_arrow_in_domain16": after_broken_key,
                       "movement_distance": broken_distance},
            "fixed": {"domain": 16, "echo_exit": 0, "before_arrow": fixed,
                      "after_arrow": fixed_moved, "movement_distance": fixed_distance},
        }
        EVIDENCE.joinpath("measurements.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
        success = True
    finally:
        if teleop is not None:
            teleop.close()
        for process in reversed(PROCESSES):
            stop(process)
        if simulator_log is not None:
            simulator_log.close()
        EVIDENCE.joinpath("commands.json").write_text(json.dumps(COMMANDS, ensure_ascii=False, indent=2) + "\n")
        if success:
            nodes(16, "nodes-cleanup-16.txt", set())
            nodes(17, "nodes-cleanup-17.txt", set())
            EVIDENCE.joinpath("commands.json").write_text(json.dumps(COMMANDS, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    if os.environ.get("ROS_DISTRO") != "lyrical":
        raise SystemExit("First run: source /opt/ros/lyrical/setup.bash")
    with tempfile.TemporaryDirectory(prefix="pr01-ros-logs-") as directory:
        LOG_DIR = Path(directory)
        main()

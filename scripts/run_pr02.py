#!/usr/bin/env python3
"""Record the PR02 launch and topic-name experiment using installed ROS 2.

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
EVIDENCE = ROOT / "evidence" / "pr02"
DOMAIN = int(os.environ.get("ROS_DOMAIN_ID", "17"))
TWIST = "{linear: {x: 1.0}, angular: {z: 0.5}}"
COMMANDS: list[dict] = []
PROCESSES: list[subprocess.Popen] = []


def environment() -> dict[str, str]:
    env = os.environ.copy()
    env["ROS_DOMAIN_ID"] = str(DOMAIN)
    env["ROS_LOG_DIR"] = "/tmp/ros-pr02-logs"
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
    if nodes("nodes-initial.txt"):
        raise RuntimeError(f"ROS domain {DOMAIN} contains other nodes")

    prefix = run(["ros2", "pkg", "prefix", "turtle_bringup"], "package-prefix.txt").strip()
    launch_file = Path(prefix) / "share/turtle_bringup/launch/sim.launch.py"
    if not launch_file.is_file():
        raise RuntimeError(f"Launch file is not installed: {launch_file}")
    run(["ros2", "interface", "show", "geometry_msgs/msg/Twist"], "twist-interface.txt")

    first_launch = start(["ros2", "launch", "turtle_bringup", "sim.launch.py"], "launch-first.txt")
    try:
        wait_for_node(first_launch, {"/turtlesim"}, "nodes-first.txt")
    finally:
        stop(first_launch)
    if nodes("nodes-after-first-stop.txt"):
        raise RuntimeError("turtlesim remained after stopping launch")

    launch = start(["ros2", "launch", "turtle_bringup", "sim.launch.py"], "launch-experiment.txt")
    try:
        wait_for_node(launch, {"/turtlesim"}, "nodes-experiment.txt")
        pose_type = run(["ros2", "topic", "type", "/turtle1/pose",
                         "--no-daemon", "--spin-time", "2"], "pose-type.txt").strip()
        before = pose("pose-before.txt", pose_type)
        run(["ros2", "topic", "pub", "--once", "/turtle1/cmd_vel",
             "geometry_msgs/msg/Twist", TWIST], "pub-once.txt")
        after_once = pose("pose-after-once.txt", pose_type)
        if distance(before, after_once) <= 0.1:
            raise RuntimeError("Correct one-shot command did not move the turtle")

        broken = start(["ros2", "topic", "pub", "--rate", "1",
                        "--wait-matching-subscriptions", "0", "/cmd_vel",
                        "geometry_msgs/msg/Twist", TWIST], "pub-broken.txt")
        try:
            time.sleep(2)
            wrong_info = run(["ros2", "topic", "info", "/cmd_vel", "--verbose"],
                             "info-broken.txt")
            run(["ros2", "topic", "info", "/turtle1/cmd_vel", "--verbose"],
                "info-correct-during-broken.txt")
            wrong_before = pose("pose-before-broken.txt", pose_type)
            time.sleep(2)
            wrong_after = pose("pose-after-broken.txt", pose_type)
            if "Subscription count: 0" not in wrong_info:
                raise RuntimeError("Wrong topic unexpectedly has a subscriber")
            if distance(wrong_before, wrong_after) > 0.001:
                raise RuntimeError("Turtle moved while publishing on /cmd_vel")
        finally:
            stop(broken)

        fixed = start(["ros2", "topic", "pub", "--rate", "1",
                       "--wait-matching-subscriptions", "0", "/turtle1/cmd_vel",
                       "geometry_msgs/msg/Twist", TWIST], "pub-fixed.txt")
        try:
            fixed_before = pose("pose-before-fixed.txt", pose_type)
            time.sleep(2)
            fixed_info = run(["ros2", "topic", "info", "/turtle1/cmd_vel", "--verbose"],
                             "info-fixed.txt")
            fixed_after = pose("pose-after-fixed.txt", pose_type)
            if "Subscription count: 1" not in fixed_info:
                raise RuntimeError("Correct topic does not have one subscriber")
            if distance(fixed_before, fixed_after) <= 0.1:
                raise RuntimeError("Turtle did not move after correcting only the name")
        finally:
            stop(fixed)
    finally:
        stop(launch)
        for process in reversed(PROCESSES):
            stop(process)

    if nodes("nodes-final.txt"):
        raise RuntimeError("Nodes remained after stopping the experiment")
    measurements = {
        "domain": DOMAIN,
        "launch_file": str(launch_file),
        "pose_type": pose_type,
        "once": {"before": before, "after": after_once,
                 "distance": distance(before, after_once)},
        "broken": {"before": wrong_before, "after": wrong_after,
                   "distance": distance(wrong_before, wrong_after)},
        "fixed": {"before": fixed_before, "after": fixed_after,
                  "distance": distance(fixed_before, fixed_after)},
    }
    (EVIDENCE / "measurements.json").write_text(json.dumps(measurements, indent=2) + "\n")
    (EVIDENCE / "commands.json").write_text(json.dumps(COMMANDS, indent=2) + "\n")
    print(json.dumps(measurements, indent=2))


if __name__ == "__main__":
    main()

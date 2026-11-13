#!/usr/bin/env python3
"""Record the PR05 live/replay QoS experiment with installed ROS 2.

Source ROS and the workspace first. Use an empty domain and a new bag path.
The simulator runs offscreen; all observations come from real ROS processes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import time

import yaml


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/pr05'
DOMAIN = int(os.environ.get('ROS_DOMAIN_ID', '20'))
TOPIC = '/robot_a/sensor_pose'
COMMANDS: list[dict] = []
PROCESSES: list[subprocess.Popen] = []


def environment() -> dict[str, str]:
    env = os.environ.copy()
    env.update(ROS_DOMAIN_ID=str(DOMAIN), ROS_LOG_DIR='/tmp/ros-pr05-logs',
               QT_QPA_PLATFORM='offscreen', PYTHONUNBUFFERED='1', RCUTILS_COLORIZED_OUTPUT='0')
    Path(env['ROS_LOG_DIR']).mkdir(parents=True, exist_ok=True)
    return env


def run(args: list[str], filename: str, expected: int = 0, timeout: int = 30) -> str:
    result = subprocess.run(args, cwd=ROOT, env=environment(), capture_output=True,
                            text=True, timeout=timeout)
    output = result.stdout + result.stderr
    (EVIDENCE / filename).write_text(output)
    COMMANDS.append({'command': shlex.join(args), 'output': filename,
                     'exit_code': result.returncode})
    if result.returncode != expected:
        raise RuntimeError(f'{shlex.join(args)}: expected {expected}, got {result.returncode}: {output}')
    return output


def start(args: list[str], filename: str) -> subprocess.Popen:
    with (EVIDENCE / filename).open('w') as output:
        process = subprocess.Popen(args, cwd=ROOT, env=environment(), stdin=subprocess.DEVNULL,
                                   stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    PROCESSES.append(process)
    COMMANDS.append({'command': shlex.join(args), 'output': filename, 'pid': process.pid})
    return process


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        # ros2 run/launch forwards SIGINT to children; signal the wrapper once.
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
    for command in COMMANDS:
        if command.get('pid') == process.pid:
            command['exit_code'] = process.returncode


def nodes(filename: str) -> set[str]:
    output = run(['ros2', 'node', 'list', '--no-daemon', '--spin-time', '2'], filename)
    return {line.strip() for line in output.splitlines() if line.startswith('/')}


def wait_for_nodes(process: subprocess.Popen, expected: set[str], filename: str) -> None:
    for _ in range(8):
        if expected and process.poll() is not None:
            raise RuntimeError('ROS process exited early; inspect its log')
        if nodes(filename) == expected:
            return
        time.sleep(0.5)
    raise RuntimeError(f'Expected nodes {expected}; see {filename}')


def echo(stage: str, reliability: str, pose_type: str) -> str:
    output = run(['timeout', '8s', 'ros2', 'topic', 'echo', TOPIC, pose_type,
                  '--qos-reliability', reliability, '--once', '--no-daemon'],
                 f'{stage}-echo.txt', expected=124 if reliability == 'reliable' else 0, timeout=12)
    if reliability == 'reliable':
        assert not re.search(r'^x:', output, re.M), 'Incompatible subscriber received a pose'
    else:
        assert re.search(r'^x:', output, re.M), 'Compatible subscriber did not receive a pose'
    return output


def topic_info(stage: str) -> str:
    return run(['ros2', 'topic', 'info', TOPIC, '--verbose', '--no-daemon', '--spin-time', '2'],
               f'{stage}-info.txt')


def counts(filename: str) -> list[int]:
    return [int(value) for value in re.findall(r'received=(\d+)', (EVIDENCE / filename).read_text())]


def aggregate(filename: str, sources: list[tuple[str, str]]) -> None:
    sections = []
    for label, source in sources:
        command = next((item for item in reversed(COMMANDS) if item['output'] == source), None)
        detail = f"$ {command['command']}\nexit={command.get('exit_code')}\n" if command else ''
        sections.append(f'=== {label} ({source}) ===\n{detail}{(EVIDENCE / source).read_text()}')
    (EVIDENCE / filename).write_text('\n'.join(sections))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bag-dir', type=Path, default=EVIDENCE / 'bag')
    args = parser.parse_args()
    bag = args.bag_dir.resolve()
    if bag.exists():
        raise RuntimeError(f'Bag already exists: {bag}; archive it or choose --bag-dir')
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    expected_live = {'/turtlesim', '/robot_a/patrol', '/robot_a/pose_relay',
                     '/robot_a/pose_subscriber'}
    measurements = {'domain': DOMAIN, 'topic': TOPIC, 'bag': str(bag.relative_to(ROOT))
                    if bag.is_relative_to(ROOT) else str(bag)}
    try:
        assert not nodes('nodes-initial.txt'), f'ROS domain {DOMAIN} contains other nodes'
        print('Live stream: reliable subscriber, recording disabled', flush=True)
        broken = start(['ros2', 'launch', 'course_bringup', 'patrol.launch.py',
                        'namespace:=robot_a', 'subscriber_reliability:=reliable', 'record:=false',
                        f'bag_dir:={bag}'], 'launch-before.txt')
        wait_for_nodes(broken, expected_live, 'nodes-before.txt')
        assert not bag.exists(), 'record:=false created a bag'
        topics = run(['ros2', 'topic', 'list', '-t', '--no-daemon', '--spin-time', '2'],
                     'topics-before.txt')
        assert TOPIC in topics and '/robot_a/cmd_vel' not in topics
        pose_type = run(['ros2', 'topic', 'type', TOPIC, '--no-daemon', '--spin-time', '2'],
                        'pose-type.txt').strip()
        measurements['pose_type'] = pose_type
        before_info = topic_info('live-before')
        assert 'BEST_EFFORT' in before_info and 'RELIABLE' in before_info
        echo('live-before', 'reliable', pose_type)
        assert counts('launch-before.txt') and max(counts('launch-before.txt')) == 0
        stop(broken)
        assert broken.returncode == 0, 'Broken configuration failed to shut down cleanly'
        wait_for_nodes(broken, set(), 'nodes-between.txt')

        print('Live stream: best_effort subscriber, recording one MCAP bag', flush=True)
        fixed = start(['ros2', 'launch', 'course_bringup', 'patrol.launch.py',
                       'namespace:=robot_a', 'subscriber_reliability:=best_effort', 'record:=true',
                       f'bag_dir:={bag}'], 'launch-after.txt')
        wait_for_nodes(fixed, expected_live | {'/rosbag2_recorder'}, 'nodes-after.txt')
        after_info = topic_info('live-after')
        echo('live-after', 'best_effort', pose_type)
        command = run(['timeout', '8s', 'ros2', 'topic', 'echo', '/turtle1/cmd_vel',
                       'geometry_msgs/msg/Twist', '--once', '--no-daemon'], 'cmd-vel.txt', timeout=12)
        assert re.search(r'x: 0\.5', command), 'Patrol command did not reach turtlesim topic'
        measurements['live_received'] = max(counts('launch-after.txt'))
        assert measurements['live_received'] > 0
        stop(fixed)
        assert fixed.returncode == 0, 'Recording launch failed to shut down cleanly'
        wait_for_nodes(fixed, set(), 'nodes-before-replay.txt')
        metadata = yaml.safe_load((bag / 'metadata.yaml').read_text())['rosbag2_bagfile_information']
        topics = metadata['topics_with_message_count']
        assert metadata['storage_identifier'] == 'mcap'
        assert len(topics) == 1 and topics[0]['topic_metadata']['name'] == TOPIC
        assert topics[0]['message_count'] > 0
        measurements['bag_message_count'] = topics[0]['message_count']
        shutil.copyfile(bag / 'metadata.yaml', EVIDENCE / 'bag-metadata.yaml')
        files = list(bag.glob('*.mcap'))
        assert len(files) == 1
        bag_sha = hashlib.sha256(files[0].read_bytes()).hexdigest()
        measurements['mcap_sha256'] = bag_sha
        run(['ros2', 'bag', 'info', str(bag)], 'bag-info.txt')

        print('Replay: same MCAP, best_effort override, both subscriber policies', flush=True)
        player = start(['ros2', 'bag', 'play', str(bag), '--loop', '--disable-keyboard-controls',
                        '--qos-profile-overrides-path', 'config/qos-overrides.yaml'], 'replay.txt')
        wait_for_nodes(player, {'/rosbag2_player'}, 'nodes-player.txt')
        replay_before = start(['ros2', 'run', 'course_bringup', 'pose_subscriber', '--ros-args',
                               '-r', '__ns:=/robot_a', '-p', 'reliability:=reliable'],
                              'subscriber-replay-before.txt')
        wait_for_nodes(replay_before, {'/rosbag2_player', '/robot_a/pose_subscriber'},
                       'nodes-replay-before.txt')
        replay_info = topic_info('replay-before')
        assert 'Publisher count: 1' in replay_info and 'BEST_EFFORT' in replay_info
        echo('replay-before', 'reliable', pose_type)
        assert counts('subscriber-replay-before.txt')
        assert max(counts('subscriber-replay-before.txt')) == 0
        stop(replay_before)
        replay_after = start(['ros2', 'run', 'course_bringup', 'pose_subscriber', '--ros-args',
                              '-r', '__ns:=/robot_a', '-p', 'reliability:=best_effort'],
                             'subscriber-replay-after.txt')
        wait_for_nodes(replay_after, {'/rosbag2_player', '/robot_a/pose_subscriber'},
                       'nodes-replay-after.txt')
        topic_info('replay-after')
        echo('replay-after', 'best_effort', pose_type)
        measurements['replay_received'] = max(counts('subscriber-replay-after.txt'))
        assert measurements['replay_received'] > 0
        stop(replay_after)
        stop(player)
        assert replay_before.returncode == replay_after.returncode == player.returncode == 0
        assert hashlib.sha256(files[0].read_bytes()).hexdigest() == bag_sha
        wait_for_nodes(player, set(), 'nodes-final.txt')
        aggregate('qos-before.txt', [
            ('Live topic is visible', 'topics-before.txt'),
            ('Live incompatible endpoints', 'live-before-info.txt'),
            ('Live reliable echo: expected timeout', 'live-before-echo.txt'),
            ('Live subscriber receives zero', 'launch-before.txt'),
            ('Replay incompatible endpoints', 'replay-before-info.txt'),
            ('Replay reliable echo: expected timeout', 'replay-before-echo.txt'),
            ('Replay subscriber receives zero', 'subscriber-replay-before.txt'),
        ])
        aggregate('qos-after.txt', [
            ('Live compatible endpoints', 'live-after-info.txt'),
            ('Live best_effort echo: pose received', 'live-after-echo.txt'),
            ('Live subscriber receives poses', 'launch-after.txt'),
            ('Replay compatible endpoints', 'replay-after-info.txt'),
            ('Replay best_effort echo: pose received', 'replay-after-echo.txt'),
            ('Replay subscriber receives poses', 'subscriber-replay-after.txt'),
            ('One recorded topic', 'bag-info.txt'),
        ])
        measurements.update(record_false_verified=True, live_reliable_exit=124,
                            live_best_effort_exit=0, replay_reliable_exit=124,
                            replay_best_effort_exit=0, replay_verified=True,
                            all_processes_stopped=True)
        (EVIDENCE / 'measurements.json').write_text(json.dumps(measurements, indent=2) + '\n')
        print(json.dumps(measurements, indent=2))
    finally:
        for process in reversed(PROCESSES):
            stop(process)
        (EVIDENCE / 'commands.json').write_text(json.dumps(COMMANDS, indent=2) + '\n')


if __name__ == '__main__':
    main()

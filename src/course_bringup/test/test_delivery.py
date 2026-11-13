"""Exercise forwarding and incompatible reliability with real DDS endpoints."""

import time

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data

from course_bringup.pose_relay import Pose, PoseRelay
from course_bringup.pose_subscriber import PoseSubscriber


def test_relay_delivers_only_to_compatible_subscriber():
    rclpy.init(args=[])
    executor = SingleThreadedExecutor()
    instances = []
    try:
        source = Node('source', namespace='pr05_test')
        instances.append(source)
        relay = PoseRelay(namespace='pr05_test')
        instances.append(relay)
        for reliability in ('reliable', 'best_effort'):
            instances.append(PoseSubscriber(
                namespace='pr05_test',
                cli_args=['--ros-args', '-r', f'__node:={reliability}_subscriber'],
                parameter_overrides=[Parameter('reliability', value=reliability)]))
        reliable, best_effort = instances[-2:]
        publisher = source.create_publisher(Pose, 'pose', 10)
        forwarded = []
        subscription = source.create_subscription(
            Pose, 'sensor_pose', forwarded.append, qos_profile_sensor_data)
        for instance in instances:
            executor.add_node(instance)
        deadline = time.monotonic() + 6.0
        message = Pose(x=4.2, y=2.1, theta=0.3)
        while time.monotonic() < deadline:
            publisher.publish(message)
            executor.spin_once(timeout_sec=0.02)
            time.sleep(0.01)
        assert subscription is not None
        assert best_effort.received > 10, 'Relay did not deliver the source stream'
        assert reliable.received == 0, 'Incompatible reliable subscriber received data'
        assert forwarded, 'Forwarded stream was empty'
        assert all(abs(pose.x - 4.2) < 1e-5 and abs(pose.y - 2.1) < 1e-5
                   for pose in forwarded), 'Relay changed the message contents'
    finally:
        for instance in reversed(instances):
            executor.remove_node(instance)
            instance.destroy_node()
        executor.shutdown()
        rclpy.shutdown()

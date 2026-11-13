"""Observe whether a chosen reliability policy receives sensor poses."""

import rclpy
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy

from course_bringup.pose_relay import Pose


class PoseSubscriber(Node):
    """Log delivery counts, including zero when endpoints are incompatible."""

    def __init__(self, **kwargs):
        super().__init__('pose_subscriber', **kwargs)
        reliability = self.declare_parameter(
            'reliability', 'best_effort',
            ParameterDescriptor(read_only=True)).value
        policies = {'reliable': ReliabilityPolicy.RELIABLE,
                    'best_effort': ReliabilityPolicy.BEST_EFFORT}
        if reliability not in policies:
            raise ValueError('reliability must be reliable or best_effort')
        self.received = 0
        self.subscription = self.create_subscription(
            Pose, 'sensor_pose', self.on_pose,
            QoSProfile(depth=10, reliability=policies[reliability]))
        self.timer = self.create_timer(1.0, self.log_count)
        self.get_logger().info(f'Subscribing with reliability={reliability}')

    def on_pose(self, message):
        self.received += 1
        if self.received == 1:
            self.get_logger().info(f'First pose: x={message.x:.6f}, y={message.y:.6f}')

    def log_count(self):
        self.get_logger().info(f'received={self.received}')


def main(args=None):
    rclpy.init(args=args)
    node = PoseSubscriber()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

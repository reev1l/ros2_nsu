"""Relay the simulator pose using a best-effort publisher."""

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

try:
    from turtlesim_msgs.msg import Pose
except ModuleNotFoundError:
    from turtlesim.msg import Pose


class PoseRelay(Node):
    """Keep topic names relative; the launch file selects the global input."""

    def __init__(self, **kwargs):
        super().__init__('pose_relay', **kwargs)
        self.publisher = self.create_publisher(Pose, 'sensor_pose', qos_profile_sensor_data)
        self.subscription = self.create_subscription(Pose, 'pose', self.on_pose, 10)
        self.get_logger().info('Publishing sensor_pose with reliability=best_effort')

    def on_pose(self, message):
        self.publisher.publish(message)


def main(args=None):
    rclpy.init(args=args)
    node = PoseRelay()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

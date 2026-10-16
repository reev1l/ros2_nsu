"""Subscribe to pose and publish commands every 0.1 seconds."""

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from geometry_msgs.msg import Twist

try:
    from turtlesim_msgs.msg import Pose
except ModuleNotFoundError:
    from turtlesim.msg import Pose

from patrol.control import command_from_pose


class Patrol(Node):
    """Store the last pose; let the timer select and publish commands."""

    def __init__(self):
        super().__init__('patrol')
        self.last_pose = None
        self.publisher = self.create_publisher(Twist, 'cmd_vel', 10)
        self.subscription = self.create_subscription(
            Pose, '/turtle1/pose', self.on_pose, 10)
        self.timer = self.create_timer(0.1, self.on_timer)

    def on_pose(self, message):
        self.last_pose = message

    def on_timer(self):
        self.publisher.publish(command_from_pose(self.last_pose))


def main(args=None):
    rclpy.init(args=args)
    node = Patrol()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

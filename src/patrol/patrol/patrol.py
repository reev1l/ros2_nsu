"""Subscribe to pose and publish commands every 0.1 seconds."""

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from geometry_msgs.msg import Twist
from rcl_interfaces.msg import SetParametersResult

try:
    from turtlesim_msgs.msg import Pose
except ModuleNotFoundError:
    from turtlesim.msg import Pose

from patrol.control import command_from_pose
from patrol.parameters import Settings, updated_settings


class Patrol(Node):
    """Store the last pose; let the timer select and publish commands."""

    def __init__(self):
        super().__init__('patrol')
        defaults = Settings()
        self.settings = updated_settings(defaults, {
            name: self.declare_parameter(name, getattr(defaults, name)).value
            for name in ('linear_speed', 'turn_rate', 'publish_hz')
        })
        self.last_pose = None
        self.publisher = self.create_publisher(Twist, 'cmd_vel', 10)
        self.subscription = self.create_subscription(
            Pose, '/turtle1/pose', self.on_pose, 10)
        self.timer = self.create_timer(1.0 / self.settings.publish_hz, self.on_timer)
        self.add_on_set_parameters_callback(self.validate_parameters)
        self.add_post_set_parameters_callback(self.apply_parameters)

    def candidate_settings(self, parameters):
        return updated_settings(self.settings, {
            parameter.name: parameter.value for parameter in parameters
            if parameter.name in ('linear_speed', 'turn_rate', 'publish_hz')
        })

    def validate_parameters(self, parameters):
        try:
            self.candidate_settings(parameters)
        except (ValueError, TypeError) as error:
            return SetParametersResult(successful=False, reason=str(error))
        return SetParametersResult(successful=True)

    def apply_parameters(self, parameters):
        # Called only after the complete parameter update was accepted.
        candidate = self.candidate_settings(parameters)
        if candidate.publish_hz != self.settings.publish_hz:
            self.timer.cancel()
            self.destroy_timer(self.timer)
            self.timer = self.create_timer(1.0 / candidate.publish_hz, self.on_timer)
        self.settings = candidate

    def on_pose(self, message):
        self.last_pose = message

    def on_timer(self):
        self.publisher.publish(command_from_pose(
            self.last_pose, self.settings.linear_speed, self.settings.turn_rate))


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

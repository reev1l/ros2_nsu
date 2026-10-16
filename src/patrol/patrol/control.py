"""Select a command without ROS side effects."""

from geometry_msgs.msg import Twist


def command_from_pose(pose, linear_speed=0.5, turn_rate=0.3):
    """Return a fresh zero command until the first pose, then the configured arc."""
    command = Twist()
    if pose is not None:
        command.linear.x = linear_speed
        command.angular.z = turn_rate
    return command

"""Select a command without ROS side effects."""

from geometry_msgs.msg import Twist


def command_from_pose(pose):
    """Return a fresh zero command until the first pose, then a fixed arc."""
    command = Twist()
    if pose is not None:
        command.linear.x = 0.5
        command.angular.z = 0.3
    return command

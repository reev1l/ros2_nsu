"""Check command selection before and after the first pose."""

try:
    from turtlesim_msgs.msg import Pose
except ModuleNotFoundError:
    from turtlesim.msg import Pose

from patrol.control import command_from_pose


def fields(command):
    return (command.linear.x, command.linear.y, command.linear.z,
            command.angular.x, command.angular.y, command.angular.z)


def test_no_pose_stops():
    assert fields(command_from_pose(None)) == (0., 0., 0., 0., 0., 0.)


def test_pose_drives_arc_without_mutating_input():
    pose = Pose(x=4., y=5., theta=1.)
    assert fields(command_from_pose(pose)) == (0.5, 0., 0., 0., 0., 0.3)
    assert (pose.x, pose.y, pose.theta) == (4., 5., 1.)


def test_commands_are_independent():
    command = command_from_pose(Pose())
    command.linear.x = 9.
    assert fields(command_from_pose(None)) == (0., 0., 0., 0., 0., 0.)
    assert command_from_pose(Pose()).linear.x == 0.5


def test_configured_command_and_stop():
    assert fields(command_from_pose(Pose(), 0.2, -0.4)) == (0.2, 0., 0., 0., 0., -0.4)
    assert fields(command_from_pose(None, 0.2, -0.4)) == (0., 0., 0., 0., 0., 0.)

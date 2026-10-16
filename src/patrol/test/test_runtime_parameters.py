"""Verify parameter transactions on a real rclpy node."""

import pytest
import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.parameter import Parameter

from patrol.patrol import Patrol


@pytest.fixture
def node():
    rclpy.init(args=[])
    instance = Patrol()
    try:
        yield instance
    finally:
        instance.destroy_node()
        rclpy.shutdown()


def test_frequency_replaces_one_timer(node):
    old = node.timer
    result = node.set_parameters_atomically([Parameter('publish_hz', value=5.0)])
    assert result.successful
    assert node.timer is not old
    assert len(list(node.timers)) == 1
    assert node.timer.timer_period_ns == 200_000_000
    assert node.settings.publish_hz == node.get_parameter('publish_hz').value == 5.0


def test_invalid_atomic_update_changes_nothing(node):
    timer = node.timer
    result = node.set_parameters_atomically([
        Parameter('linear_speed', value=0.8), Parameter('publish_hz', value=0.0)])
    assert not result.successful
    assert node.timer is timer
    assert node.get_parameter('linear_speed').value == node.settings.linear_speed == 0.5
    assert node.get_parameter('publish_hz').value == node.settings.publish_hz == 10.0
    assert not timer.is_canceled()


def test_rejected_by_another_validator_has_no_side_effects(node):
    timer = node.timer
    node.add_on_set_parameters_callback(
        lambda parameters: SetParametersResult(successful=False, reason='test rejection'))
    result = node.set_parameters_atomically([Parameter('publish_hz', value=5.0)])
    assert not result.successful
    assert node.timer is timer
    assert node.settings.publish_hz == node.get_parameter('publish_hz').value == 10.0
    assert not timer.is_canceled()

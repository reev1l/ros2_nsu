"""Validate a complete candidate configuration without changing node state."""

from dataclasses import dataclass, replace
import math


@dataclass(frozen=True)
class Settings:
    linear_speed: float = 0.5
    turn_rate: float = 0.3
    publish_hz: float = 10.0


def validate_settings(settings):
    """Reject nonfinite values and values outside the practice bounds."""
    for name, lower, upper in (
        ('linear_speed', 0., 1.), ('turn_rate', -1., 1.),
        ('publish_hz', 1., 30.),
    ):
        value = getattr(settings, name)
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not lower <= value <= upper):
            raise ValueError(f'{name} must be finite and in [{lower}, {upper}]')
    return settings


def updated_settings(current, changes):
    """Validate all proposed values together; leave current settings intact."""
    return validate_settings(replace(current, **changes))

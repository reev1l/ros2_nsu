"""Check limits, invalid updates and preservation of active configuration."""

import pytest

from patrol.parameters import Settings, updated_settings, validate_settings


def test_change_ten_to_five():
    old = Settings()
    new = updated_settings(old, {'publish_hz': 5.0})
    assert old.publish_hz == 10.0
    assert new.publish_hz == 5.0
    assert 1.0 / new.publish_hz == 0.2


@pytest.mark.parametrize('name,value', [
    ('publish_hz', 0.), ('publish_hz', -1.), ('publish_hz', float('nan')),
    ('publish_hz', float('inf')), ('publish_hz', 30.1), ('publish_hz', 0.9),
    ('linear_speed', -0.1), ('linear_speed', 1.1),
    ('turn_rate', -1.1), ('turn_rate', 1.1),
    ('linear_speed', float('nan')), ('turn_rate', float('inf')),
])
def test_invalid_update_preserves_current(name, value):
    current = Settings()
    with pytest.raises(ValueError):
        updated_settings(current, {name: value})
    assert current == Settings()


@pytest.mark.parametrize('settings', [Settings(0., -1., 1.), Settings(1., 1., 30.)])
def test_inclusive_boundaries(settings):
    assert validate_settings(settings) == settings


def test_mixed_update_is_rejected_as_a_whole():
    current = Settings()
    with pytest.raises(ValueError):
        updated_settings(current, {'linear_speed': 0.8, 'publish_hz': 0.})
    assert current == Settings()

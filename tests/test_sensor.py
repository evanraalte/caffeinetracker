"""Integration tests for sensor entities and service calls."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.caffeine_tracker.const import (
    CONF_HALF_LIFE_HOURS,
    CONF_PERSON_NAME,
    CONF_SLEEP_SAFE_MG,
    DOMAIN,
)
from custom_components.caffeine_tracker.coordinator import CaffeineCoordinator


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Erik",
        data={
            CONF_PERSON_NAME: "Erik",
            CONF_HALF_LIFE_HOURS: 5.0,
            CONF_SLEEP_SAFE_MG: 50.0,
        },
        entry_id="test_entry_erik",
    )


@pytest.fixture
def mock_store():
    with patch("custom_components.caffeine_tracker.coordinator.Store") as cls:
        inst = AsyncMock()
        inst.async_load.return_value = None
        inst.async_save.return_value = None
        cls.return_value = inst
        yield inst


async def test_sensors_created(
    hass: HomeAssistant, entry: MockConfigEntry, mock_store
) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    level = hass.states.get("sensor.erik_caffeine_level")
    today = hass.states.get("sensor.erik_caffeine_consumed_today")
    count = hass.states.get("sensor.erik_consumptions_today")
    safe = hass.states.get("sensor.erik_sleep_safe_at")

    assert level is not None
    assert today is not None
    assert count is not None
    assert safe is not None


async def test_initial_sensor_values_are_zero(
    hass: HomeAssistant, entry: MockConfigEntry, mock_store
) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert float(hass.states.get("sensor.erik_caffeine_level").state) == 0.0
    assert float(hass.states.get("sensor.erik_caffeine_consumed_today").state) == 0.0
    assert int(hass.states.get("sensor.erik_consumptions_today").state) == 0


async def test_consumption_count(
    hass: HomeAssistant, entry: MockConfigEntry, mock_store
) -> None:
    """Test that consumption count increments correctly."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Log 2 events
    await hass.services.async_call(
        DOMAIN,
        "log_consumption",
        {"mg": 80.0, "label": "espresso"},
        target={"entity_id": "sensor.erik_caffeine_level"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "log_consumption",
        {"mg": 40.0, "label": "tea"},
        target={"entity_id": "sensor.erik_caffeine_level"},
        blocking=True,
    )
    await hass.async_block_till_done()

    count = int(hass.states.get("sensor.erik_consumptions_today").state)
    assert count == 2


async def test_log_consumption_service(
    hass: HomeAssistant, entry: MockConfigEntry, mock_store
) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "log_consumption",
        {"mg": 80.0, "label": "espresso"},
        target={"entity_id": "sensor.erik_caffeine_level"},
        blocking=True,
    )
    await hass.async_block_till_done()

    level = float(hass.states.get("sensor.erik_caffeine_level").state)
    assert level > 79.0  # freshly logged, close to 80 mg


async def test_log_consumption_with_label(
    hass: HomeAssistant, entry: MockConfigEntry, mock_store
) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "log_consumption",
        {"mg": 80.0, "label": "Espresso"},
        target={"entity_id": "sensor.erik_caffeine_level"},
        blocking=True,
    )
    await hass.async_block_till_done()

    level = float(hass.states.get("sensor.erik_caffeine_level").state)
    assert level > 79.0


async def test_remove_last_service(
    hass: HomeAssistant, entry: MockConfigEntry, mock_store
) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Log then remove
    await hass.services.async_call(
        DOMAIN,
        "log_consumption",
        {"mg": 80.0, "label": "Espresso"},
        target={"entity_id": "sensor.erik_caffeine_level"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "remove_last_consumption",
        {},
        target={"entity_id": "sensor.erik_caffeine_level"},
        blocking=True,
    )
    await hass.async_block_till_done()

    level = float(hass.states.get("sensor.erik_caffeine_level").state)
    assert level == 0.0


async def test_clear_today_service(
    hass: HomeAssistant, entry: MockConfigEntry, mock_store
) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "log_consumption",
        {"mg": 95.0, "label": "Filter coffee"},
        target={"entity_id": "sensor.erik_caffeine_level"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "clear_today",
        {},
        target={"entity_id": "sensor.erik_caffeine_level"},
        blocking=True,
    )
    await hass.async_block_till_done()

    today = float(hass.states.get("sensor.erik_caffeine_consumed_today").state)
    assert today == 0.0


async def test_log_consumption_device_target_only_once(
    hass: HomeAssistant, entry: MockConfigEntry, mock_store
) -> None:
    """Test that targeting a device only logs consumption once even with multiple entities."""
    from homeassistant.helpers import device_registry as dr

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Find the device ID for our config entry
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert device is not None

    # Call service targeting the device
    await hass.services.async_call(
        DOMAIN,
        "log_consumption",
        {"mg": 100.0, "label": "Device coffee"},
        target={"device_id": device.id},
        blocking=True,
    )
    await hass.async_block_till_done()

    # If it fired 3 times, level would be 300. If once, 100.
    level = float(hass.states.get("sensor.erik_caffeine_level").state)
    assert level == 100.0

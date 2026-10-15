"""Integration tests for the config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.caffeine_tracker.const import (
    CONF_ABSORPTION_TIME_MIN,
    CONF_ENABLE_ABSORPTION,
    CONF_HALF_LIFE_HOURS,
    CONF_PERSON_NAME,
    CONF_SLEEP_SAFE_MG,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def bypass_setup():
    """Skip actual integration setup — we only test the flow here."""
    with patch(
        "custom_components.caffeine_tracker.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_user_step_creates_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PERSON_NAME: "Erik",
            CONF_HALF_LIFE_HOURS: 5.0,
            CONF_SLEEP_SAFE_MG: 50.0,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Erik"
    assert result["data"][CONF_PERSON_NAME] == "Erik"
    assert result["data"][CONF_HALF_LIFE_HOURS] == 5.0
    assert result["data"][CONF_SLEEP_SAFE_MG] == 50.0


async def test_duplicate_name_shows_error(hass: HomeAssistant) -> None:
    # Create first entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PERSON_NAME: "Erik", CONF_HALF_LIFE_HOURS: 5.0, CONF_SLEEP_SAFE_MG: 50.0},
    )

    # Attempt duplicate
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_PERSON_NAME: "erik", CONF_HALF_LIFE_HOURS: 5.0, CONF_SLEEP_SAFE_MG: 50.0},
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "name_taken"


async def test_multiple_persons_allowed(hass: HomeAssistant) -> None:
    for name in ("Erik", "Girlfriend"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PERSON_NAME: name,
                CONF_HALF_LIFE_HOURS: 5.0,
                CONF_SLEEP_SAFE_MG: 50.0,
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2


async def test_options_flow_updates_settings(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Erik",
        data={
            CONF_PERSON_NAME: "Erik",
            CONF_HALF_LIFE_HOURS: 5.0,
            CONF_SLEEP_SAFE_MG: 50.0,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_HALF_LIFE_HOURS: 6.0,
            CONF_SLEEP_SAFE_MG: 40.0,
            CONF_ENABLE_ABSORPTION: True,
            CONF_ABSORPTION_TIME_MIN: 20.0,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_HALF_LIFE_HOURS] == 6.0
    assert entry.options[CONF_ENABLE_ABSORPTION] is True


async def test_sleep_safe_threshold_must_be_positive(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PERSON_NAME: "Erik",
                CONF_HALF_LIFE_HOURS: 5.0,
                CONF_SLEEP_SAFE_MG: 0,
            },
        )

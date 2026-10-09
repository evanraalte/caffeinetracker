"""The Caffeine Tracker integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, service
import homeassistant.util.dt as dt_util
import voluptuous as vol

from .const import (
    ATTR_EVENT_ID,
    ATTR_LABEL,
    ATTR_MG,
    ATTR_TIMESTAMP,
    CONF_ABSORPTION_TIME_MIN,
    CONF_ENABLE_ABSORPTION,
    CONF_HALF_LIFE_HOURS,
    CONF_PERSON_NAME,
    CONF_SLEEP_SAFE_MG,
    DEFAULT_ABSORPTION_TIME_MIN,
    DEFAULT_ENABLE_ABSORPTION,
    DEFAULT_HALF_LIFE_HOURS,
    DEFAULT_SLEEP_SAFE_MG,
    DOMAIN,
    SERVICE_CLEAR_TODAY,
    SERVICE_LOG_CONSUMPTION,
    SERVICE_REMOVE_BY_ID,
    SERVICE_REMOVE_LAST,
)
from .coordinator import CaffeineCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Caffeine Tracker integration."""

    async def handle_service(call: ServiceCall) -> None:
        """Handle the service call."""
        # This helper extracts unique config entry IDs from the target (entities or devices).
        # By iterating over entry IDs, we ensure the action fires exactly once per profile.
        entry_ids = await service.async_extract_config_entry_ids(call)

        for entry_id in entry_ids:
            if entry_id not in hass.data.get(DOMAIN, {}):
                continue
            coordinator: CaffeineCoordinator = hass.data[DOMAIN][entry_id]

            if call.service == SERVICE_LOG_CONSUMPTION:
                mg = call.data[ATTR_MG]
                label = call.data.get(ATTR_LABEL, "custom")
                timestamp_str = call.data.get(ATTR_TIMESTAMP)
                ts = None
                if timestamp_str:
                    ts = dt_util.parse_datetime(timestamp_str)
                    if ts and ts.tzinfo is None:
                        ts = dt_util.as_utc(ts)

                await coordinator.async_log_consumption(
                    mg=mg, label=label, timestamp=ts
                )

            elif call.service == SERVICE_REMOVE_LAST:
                await coordinator.async_remove_last()

            elif call.service == SERVICE_REMOVE_BY_ID:
                await coordinator.async_remove_by_id(call.data[ATTR_EVENT_ID])

            elif call.service == SERVICE_CLEAR_TODAY:
                await coordinator.async_clear_today()

    # Register domain-level services once at setup.
    # make_entity_service_schema adds standard target fields (entity_id, device_id, etc.)
    hass.services.async_register(
        DOMAIN,
        SERVICE_LOG_CONSUMPTION,
        handle_service,
        schema=cv.make_entity_service_schema(
            {
                vol.Required(ATTR_MG): vol.All(
                    vol.Coerce(float), vol.Range(min=1, max=2000)
                ),
                vol.Optional(ATTR_LABEL): cv.string,
                vol.Optional(ATTR_TIMESTAMP): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_LAST,
        handle_service,
        schema=cv.make_entity_service_schema({}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_BY_ID,
        handle_service,
        schema=cv.make_entity_service_schema({vol.Required(ATTR_EVENT_ID): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_TODAY,
        handle_service,
        schema=cv.make_entity_service_schema({}),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Caffeine Tracker profile from a config entry."""
    options = entry.options
    data = entry.data

    def _get_float(key: str, default: float) -> float:
        return float(options.get(key, data.get(key, default)))

    def _get_bool(key: str, default: bool) -> bool:
        return bool(options.get(key, data.get(key, default)))

    coordinator = CaffeineCoordinator(
        hass=hass,
        entry_id=entry.entry_id,
        person_name=data[CONF_PERSON_NAME],
        half_life_hours=_get_float(CONF_HALF_LIFE_HOURS, DEFAULT_HALF_LIFE_HOURS),
        sleep_safe_mg=_get_float(CONF_SLEEP_SAFE_MG, DEFAULT_SLEEP_SAFE_MG),
        enable_absorption=_get_bool(CONF_ENABLE_ABSORPTION, DEFAULT_ENABLE_ABSORPTION),
        absorption_time_min=_get_float(
            CONF_ABSORPTION_TIME_MIN, DEFAULT_ABSORPTION_TIME_MIN
        ),
    )

    await coordinator.async_load()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when options change so coordinator picks up new settings.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)

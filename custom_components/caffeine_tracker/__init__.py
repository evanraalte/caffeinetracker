"""The Caffeine Tracker integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
import inspect
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
import homeassistant.util.dt as dt_util

if TYPE_CHECKING:
    import probatio as vol
else:
    try:  # HA 2026.10+ validates schemas with probatio
        import probatio as vol
    except ImportError:  # older HA
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

# Newer HA versions dropped the hass argument from async_extract_config_entry_ids.
_extract_config_entry_ids: Callable[..., Awaitable[set[str]]] = (
    service.async_extract_config_entry_ids
)
_EXTRACT_TAKES_HASS = "hass" in inspect.signature(_extract_config_entry_ids).parameters

# Allow for small clock differences between HA and whatever sends the timestamp.
_FUTURE_TOLERANCE = timedelta(minutes=1)


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse an optional ISO 8601 timestamp into UTC; None means "now"."""
    if not value:
        return None
    try:
        ts = dt_util.parse_datetime(value)
    except ValueError:  # well-formed but impossible, e.g. month 13
        ts = None
    if ts is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="invalid_timestamp"
        )
    # Naive timestamps are taken as HA's local time zone.
    ts = dt_util.as_utc(ts)
    if ts > dt_util.utcnow() + _FUTURE_TOLERANCE:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="future_timestamp"
        )
    return ts


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Caffeine Tracker integration."""

    async def handle_service(call: ServiceCall) -> None:
        """Handle the service call."""
        # This helper extracts unique config entry IDs from the target (entities or devices).
        # By iterating over entry IDs, we ensure the action fires exactly once per profile.
        extract_args: tuple[Any, ...] = (hass, call) if _EXTRACT_TAKES_HASS else (call,)
        entry_ids = await _extract_config_entry_ids(*extract_args)

        # Validate before touching any profile so a bad call logs nothing at all.
        ts = None
        if call.service == SERVICE_LOG_CONSUMPTION:
            ts = _parse_timestamp(call.data.get(ATTR_TIMESTAMP))

        for entry_id in entry_ids:
            if entry_id not in hass.data.get(DOMAIN, {}):
                continue
            coordinator: CaffeineCoordinator = hass.data[DOMAIN][entry_id]

            if call.service == SERVICE_LOG_CONSUMPTION:
                mg = call.data[ATTR_MG]
                label = call.data.get(ATTR_LABEL, "custom")
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

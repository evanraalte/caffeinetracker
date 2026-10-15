"""Config flow for Caffeine Tracker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant import config_entries
from homeassistant.helpers import selector

if TYPE_CHECKING:
    import probatio as vol
else:
    try:  # HA 2026.10+ validates schemas with probatio
        import probatio as vol
    except ImportError:  # older HA
        import voluptuous as vol

from .const import (
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
    MAX_ABSORPTION_TIME_MIN,
    MAX_HALF_LIFE_HOURS,
    MIN_ABSORPTION_TIME_MIN,
    MIN_HALF_LIFE_HOURS,
    MIN_SLEEP_SAFE_MG,
)


def _settings_schema(
    default_half_life: float = DEFAULT_HALF_LIFE_HOURS,
    default_sleep_safe: float = DEFAULT_SLEEP_SAFE_MG,
    default_enable_absorption: bool = DEFAULT_ENABLE_ABSORPTION,
    default_absorption_time: float = DEFAULT_ABSORPTION_TIME_MIN,
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_HALF_LIFE_HOURS, default=default_half_life
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_HALF_LIFE_HOURS,
                    max=MAX_HALF_LIFE_HOURS,
                    step=0.5,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="h",
                )
            ),
            vol.Required(
                CONF_SLEEP_SAFE_MG, default=default_sleep_safe
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SLEEP_SAFE_MG,
                    max=500,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="mg",
                )
            ),
            vol.Required(
                CONF_ENABLE_ABSORPTION, default=default_enable_absorption
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_ABSORPTION_TIME_MIN, default=default_absorption_time
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_ABSORPTION_TIME_MIN,
                    max=MAX_ABSORPTION_TIME_MIN,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )
            ),
        }
    )


class CaffeineTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Caffeine Tracker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            existing_names = {
                entry.data[CONF_PERSON_NAME].lower()
                for entry in self._async_current_entries()
            }
            if user_input[CONF_PERSON_NAME].lower() in existing_names:
                errors["base"] = "name_taken"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_PERSON_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PERSON_NAME): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                    ),
                }
            ).extend(_settings_schema().schema),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> CaffeineTrackerOptionsFlow:
        return CaffeineTrackerOptionsFlow(config_entry)


class CaffeineTrackerOptionsFlow(config_entries.OptionsFlow):
    """Handle options (re-configuration) for an existing entry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        # HA < 2024.11 doesn't set self.config_entry on options flows, and assigning
        # it is deprecated in newer HA (breaks in 2025.12), so keep our own reference.
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        def _get(key: str, default: float | bool) -> float | bool:
            return self._entry.options.get(key, self._entry.data.get(key, default))

        current_half_life = float(_get(CONF_HALF_LIFE_HOURS, DEFAULT_HALF_LIFE_HOURS))
        current_sleep_safe = float(_get(CONF_SLEEP_SAFE_MG, DEFAULT_SLEEP_SAFE_MG))
        current_enable_absorption = bool(
            _get(CONF_ENABLE_ABSORPTION, DEFAULT_ENABLE_ABSORPTION)
        )
        current_absorption_time = float(
            _get(CONF_ABSORPTION_TIME_MIN, DEFAULT_ABSORPTION_TIME_MIN)
        )

        return self.async_show_form(
            step_id="init",
            data_schema=_settings_schema(
                current_half_life,
                current_sleep_safe,
                current_enable_absorption,
                current_absorption_time,
            ),
        )

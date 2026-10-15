"""Constants for the Caffeine Tracker integration."""

from __future__ import annotations

DOMAIN = "caffeine_tracker"
STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = "caffeine_tracker"

DEFAULT_HALF_LIFE_HOURS = 5.0
DEFAULT_SLEEP_SAFE_MG = 50.0
# Caffeine never decays to exactly 0 mg, so the threshold must be positive
MIN_SLEEP_SAFE_MG = 1.0
MIN_HALF_LIFE_HOURS = 3.0
MAX_HALF_LIFE_HOURS = 10.0
# Events older than this multiple of half-life contribute < 1% — safe to prune
MAX_EVENT_AGE_MULTIPLIER = 7

CONF_ENABLE_ABSORPTION = "enable_absorption"
CONF_ABSORPTION_TIME_MIN = "absorption_time_min"
DEFAULT_ENABLE_ABSORPTION = False
DEFAULT_ABSORPTION_TIME_MIN = 15.0
MIN_ABSORPTION_TIME_MIN = 5.0
MAX_ABSORPTION_TIME_MIN = 60.0

CONF_PERSON_NAME = "person_name"
CONF_HALF_LIFE_HOURS = "half_life_hours"
CONF_SLEEP_SAFE_MG = "sleep_safe_mg"

ATTR_EVENTS = "events"
ATTR_EVENT_ID = "event_id"
ATTR_MG = "mg"
ATTR_LABEL = "label"
ATTR_TIMESTAMP = "timestamp"

SERVICE_LOG_CONSUMPTION = "log_consumption"
SERVICE_REMOVE_LAST = "remove_last_consumption"
SERVICE_REMOVE_BY_ID = "remove_consumption"
SERVICE_CLEAR_TODAY = "clear_today"

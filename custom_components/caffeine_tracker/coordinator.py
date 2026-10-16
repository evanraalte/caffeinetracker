"""Caffeine Tracker data coordinator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import logging
import math
from typing import Any
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util

from .const import (
    DEFAULT_ABSORPTION_TIME_MIN,
    DEFAULT_HALF_LIFE_HOURS,
    DEFAULT_SLEEP_SAFE_MG,
    DOMAIN,
    MAX_EVENT_AGE_MULTIPLIER,
    MIN_SLEEP_SAFE_MG,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)


@dataclass
class CaffeineEvent:
    id: str
    timestamp: datetime  # UTC, timezone-aware
    mg: float
    label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "mg": self.mg,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CaffeineEvent:
        ts = datetime.fromisoformat(data["timestamp"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return cls(
            id=data["id"],
            timestamp=ts,
            mg=float(data["mg"]),
            label=data.get("label", "unknown"),
        )


@dataclass
class CaffeineData:
    current_mg: float
    consumed_today_mg: float
    consumed_today_count: int
    # None = already below threshold (safe now)
    sleep_safe_at: datetime | None
    # Only set when absorption model is enabled
    peak_mg: float | None = None
    events: list[CaffeineEvent] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure computation functions — easy to unit-test without HA mocks
# ---------------------------------------------------------------------------


def compute_current_mg(
    events: list[CaffeineEvent],
    half_life_hours: float,
    now: datetime,
    absorption_time_min: float = 0.0,
) -> float:
    """Exponential decay sum; with optional absorption ramp (1 - e^(-t/t_abs))."""
    hl_seconds = half_life_hours * 3600
    total = 0.0
    for event in events:
        elapsed = max(0.0, (now - event.timestamp).total_seconds())
        if absorption_time_min > 0:
            absorbed = 1.0 - math.exp(-elapsed / (absorption_time_min * 60))
        else:
            absorbed = 1.0
        total += event.mg * absorbed * (0.5 ** (elapsed / hl_seconds))
    return total


def compute_peak_mg(
    events: list[CaffeineEvent],
    half_life_hours: float,
    absorption_time_min: float,
    now: datetime,
) -> float:
    """Find the maximum caffeine level from now forward (absorption model only).

    Scans at 1-min steps up to 3 hours; stops early once the curve is clearly declining.
    """
    peak = compute_current_mg(events, half_life_hours, now, absorption_time_min)
    for minutes in range(1, 181):
        level = compute_current_mg(
            events,
            half_life_hours,
            now + timedelta(minutes=minutes),
            absorption_time_min,
        )
        if level > peak:
            peak = level
        elif level < peak * 0.98:
            break
    return peak


def compute_sleep_safe_at(
    current_mg: float,
    half_life_hours: float,
    sleep_safe_mg: float,
    now: datetime,
) -> datetime | None:
    """Return the future datetime when level crosses threshold, or None if already safe."""
    threshold = max(sleep_safe_mg, MIN_SLEEP_SAFE_MG)
    if current_mg <= threshold:
        return None
    hours_needed = half_life_hours * math.log2(current_mg / threshold)
    return now + timedelta(hours=hours_needed)


def compute_sleep_safe_at_absorbing(
    events: list[CaffeineEvent],
    half_life_hours: float,
    absorption_time_min: float,
    sleep_safe_mg: float,
    now: datetime,
) -> datetime | None:
    """Like compute_sleep_safe_at, but for the absorption model.

    While caffeine is still being absorbed the level can rise, so scan forward
    minute by minute until every event is ≥99% absorbed (5 time constants). From
    there the curve is plain exponential decay of the full dose.
    """
    threshold = max(sleep_safe_mg, MIN_SLEEP_SAFE_MG)
    settle = timedelta(minutes=5 * absorption_time_min)
    settled_at = max([now] + [e.timestamp + settle for e in events])

    last_above: datetime | None = None
    t = now
    while t < settled_at:
        level = compute_current_mg(events, half_life_hours, t, absorption_time_min)
        if level > threshold:
            last_above = t
        t += timedelta(minutes=1)

    settled_level = compute_current_mg(
        events, half_life_hours, settled_at, absorption_time_min
    )
    if settled_level > threshold:
        # Once absorbed, the curve is plain decay of the full dose, so the
        # no-absorption formula gives the crossing time exactly.
        fully_absorbed_mg = compute_current_mg(events, half_life_hours, now)
        return compute_sleep_safe_at(fully_absorbed_mg, half_life_hours, threshold, now)
    if last_above is None:
        return None
    return last_above + timedelta(minutes=1)


def compute_consumed_today_mg(
    events: list[CaffeineEvent], midnight_utc: datetime
) -> float:
    """Sum of caffeine consumed since local midnight (expressed as UTC)."""
    return sum(e.mg for e in events if e.timestamp >= midnight_utc)


def compute_consumed_today_count(
    events: list[CaffeineEvent], midnight_utc: datetime
) -> int:
    """Number of caffeine events since local midnight (expressed as UTC)."""
    return sum(1 for e in events if e.timestamp >= midnight_utc)


def local_midnight_utc(now_utc: datetime) -> datetime:
    """Return today's local midnight as a UTC datetime."""
    local_now = dt_util.as_local(now_utc)
    midnight_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt_util.as_utc(midnight_local)


def compute_prune_cutoff(now_utc: datetime, half_life_hours: float) -> datetime:
    """Events at or before this time can be dropped.

    Never later than local midnight, so the "consumed today" sensors keep every
    event from today even when a short half-life would allow pruning it.
    """
    decayed = now_utc - timedelta(hours=MAX_EVENT_AGE_MULTIPLIER * half_life_hours)
    return min(decayed, local_midnight_utc(now_utc))


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


class CaffeineCoordinator(DataUpdateCoordinator[CaffeineData]):
    """Manages caffeine state for one person."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        person_name: str,
        half_life_hours: float = DEFAULT_HALF_LIFE_HOURS,
        sleep_safe_mg: float = DEFAULT_SLEEP_SAFE_MG,
        enable_absorption: bool = False,
        absorption_time_min: float = DEFAULT_ABSORPTION_TIME_MIN,
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{person_name}",
            update_interval=SCAN_INTERVAL,
        )
        self.entry_id = entry_id
        self.person_name = person_name
        self.half_life_hours = half_life_hours
        self.sleep_safe_mg = sleep_safe_mg
        self.enable_absorption = enable_absorption
        self.absorption_time_min = absorption_time_min
        self._store: Store = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}_{entry_id}"
        )
        self._events: list[CaffeineEvent] = []

    async def async_load(self) -> None:
        """Load persisted events from storage."""
        stored = await self._store.async_load()
        if stored and "events" in stored:
            self._events = [CaffeineEvent.from_dict(e) for e in stored["events"]]
        self._prune_old_events()
        _LOGGER.debug("Loaded %d events for %s", len(self._events), self.person_name)

    async def _async_save(self) -> None:
        await self._store.async_save({"events": [e.to_dict() for e in self._events]})

    def _prune_old_events(self) -> None:
        cutoff = compute_prune_cutoff(dt_util.utcnow(), self.half_life_hours)
        before = len(self._events)
        self._events = [e for e in self._events if e.timestamp > cutoff]
        pruned = before - len(self._events)
        if pruned:
            _LOGGER.debug("Pruned %d stale events for %s", pruned, self.person_name)

    async def _async_update_data(self) -> CaffeineData:
        self._prune_old_events()
        now = dt_util.utcnow()
        abs_min = self.absorption_time_min if self.enable_absorption else 0.0
        current = compute_current_mg(self._events, self.half_life_hours, now, abs_min)
        midnight = local_midnight_utc(now)
        today_mg = compute_consumed_today_mg(self._events, midnight)
        today_count = compute_consumed_today_count(self._events, midnight)

        if self.enable_absorption:
            peak = compute_peak_mg(
                self._events, self.half_life_hours, self.absorption_time_min, now
            )
            # Level may still be rising, so scan forward instead of decaying from now
            safe_at = compute_sleep_safe_at_absorbing(
                self._events,
                self.half_life_hours,
                self.absorption_time_min,
                self.sleep_safe_mg,
                now,
            )
        else:
            peak = None
            safe_at = compute_sleep_safe_at(
                current, self.half_life_hours, self.sleep_safe_mg, now
            )

        return CaffeineData(
            current_mg=round(current, 1),
            consumed_today_mg=round(today_mg, 1),
            consumed_today_count=today_count,
            sleep_safe_at=safe_at,
            peak_mg=round(peak, 1) if peak is not None else None,
            events=list(self._events),
        )

    # ------------------------------------------------------------------
    # Service handlers (called by sensor entity methods)
    # ------------------------------------------------------------------

    async def async_log_consumption(
        self,
        mg: float,
        label: str,
        timestamp: datetime | None = None,
    ) -> str:
        """Record a caffeine intake event. Returns the new event ID."""
        event = CaffeineEvent(
            id=str(uuid.uuid4()),
            timestamp=timestamp or dt_util.utcnow(),
            mg=mg,
            label=label,
        )
        self._events.append(event)
        await self._async_save()
        await self.async_refresh()
        _LOGGER.info("Logged %.0f mg (%s) for %s", mg, label, self.person_name)
        return event.id

    async def async_remove_last(self) -> bool:
        """Remove the most recently logged event. Returns True if an event was removed.

        Uses log order, not timestamp order, so undo after backfilling an earlier
        drink removes that drink rather than the latest one by time.
        """
        if not self._events:
            return False
        # _events is only ever appended to or filtered, so it stays in log order.
        removed = self._events.pop()
        await self._async_save()
        await self.async_refresh()
        _LOGGER.info(
            "Removed last event (%s %.0f mg) for %s",
            removed.label,
            removed.mg,
            self.person_name,
        )
        return True

    async def async_remove_by_id(self, event_id: str) -> bool:
        """Remove an event by ID. Returns True if found and removed."""
        original = len(self._events)
        self._events = [e for e in self._events if e.id != event_id]
        if len(self._events) == original:
            return False
        await self._async_save()
        await self.async_refresh()
        _LOGGER.info("Removed event %s for %s", event_id, self.person_name)
        return True

    async def async_clear_today(self) -> None:
        """Remove all events from today (local time)."""
        now = dt_util.utcnow()
        midnight = local_midnight_utc(now)
        self._events = [e for e in self._events if e.timestamp < midnight]
        await self._async_save()
        await self.async_refresh()
        _LOGGER.info("Cleared today's events for %s", self.person_name)

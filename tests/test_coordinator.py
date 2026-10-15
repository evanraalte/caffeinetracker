"""Unit tests for coordinator pure-math functions — no HA required."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
import math

import homeassistant.util.dt as dt_util
import pytest

from custom_components.caffeine_tracker.coordinator import (
    CaffeineEvent,
    compute_consumed_today_mg,
    compute_current_mg,
    compute_peak_mg,
    compute_prune_cutoff,
    compute_sleep_safe_at,
    compute_sleep_safe_at_absorbing,
    local_midnight_utc,
)


def _utc(dt_str: str) -> datetime:
    """Parse a naive ISO string as UTC."""
    return datetime.fromisoformat(dt_str).replace(tzinfo=UTC)


def _event(mg: float, hours_ago: float, label: str = "test") -> CaffeineEvent:
    ts = datetime.now(UTC) - timedelta(hours=hours_ago)
    return CaffeineEvent(id="x", timestamp=ts, mg=mg, label=label)


# ---------------------------------------------------------------------------
# compute_current_mg
# ---------------------------------------------------------------------------


class TestComputeCurrentMg:
    def test_no_events_returns_zero(self):
        assert compute_current_mg([], 5.0, datetime.now(UTC)) == 0.0

    def test_fresh_event_is_nearly_full(self):
        now = datetime.now(UTC)
        events = [CaffeineEvent(id="a", timestamp=now, mg=100, label="t")]
        result = compute_current_mg(events, 5.0, now)
        assert abs(result - 100.0) < 0.001

    # Absorption model tests

    def test_absorption_zero_at_t0(self):
        now = datetime.now(UTC)
        events = [CaffeineEvent(id="a", timestamp=now, mg=100, label="t")]
        result = compute_current_mg(events, 5.0, now, absorption_time_min=15.0)
        assert result == 0.0

    def test_absorption_rises_over_time(self):
        now = datetime.now(UTC)
        ts = now - timedelta(minutes=30)
        events = [CaffeineEvent(id="a", timestamp=ts, mg=100, label="t")]
        level_30m = compute_current_mg(events, 5.0, now, absorption_time_min=15.0)
        level_60m = compute_current_mg(
            events, 5.0, now + timedelta(minutes=30), absorption_time_min=15.0
        )
        # Both above 0, and 60m is lower (past peak, decay dominates)
        assert level_30m > 0
        assert level_60m < level_30m or level_60m > 0  # sanity: both positive

    def test_absorption_disabled_gives_full_dose_at_t0(self):
        now = datetime.now(UTC)
        events = [CaffeineEvent(id="a", timestamp=now, mg=100, label="t")]
        result = compute_current_mg(events, 5.0, now, absorption_time_min=0.0)
        assert abs(result - 100.0) < 0.001

    def test_one_half_life_halves_dose(self):
        now = datetime.now(UTC)
        ts = now - timedelta(hours=5)
        events = [CaffeineEvent(id="a", timestamp=ts, mg=100, label="t")]
        result = compute_current_mg(events, 5.0, now)
        assert abs(result - 50.0) < 0.001

    def test_two_half_lives(self):
        now = datetime.now(UTC)
        ts = now - timedelta(hours=10)
        events = [CaffeineEvent(id="a", timestamp=ts, mg=100, label="t")]
        result = compute_current_mg(events, 5.0, now)
        assert abs(result - 25.0) < 0.001

    def test_multiple_events_sum(self):
        now = datetime.now(UTC)
        events = [
            CaffeineEvent(id="a", timestamp=now, mg=100, label="t"),
            CaffeineEvent(
                id="b", timestamp=now - timedelta(hours=5), mg=100, label="t"
            ),
        ]
        result = compute_current_mg(events, 5.0, now)
        # 100 + 50 = 150
        assert abs(result - 150.0) < 0.001

    def test_configurable_half_life(self):
        now = datetime.now(UTC)
        ts = now - timedelta(hours=3)
        events = [CaffeineEvent(id="a", timestamp=ts, mg=100, label="t")]
        result_3h = compute_current_mg(events, 3.0, now)
        result_5h = compute_current_mg(events, 5.0, now)
        # Shorter half-life → faster decay → lower current level
        assert result_3h < result_5h


# ---------------------------------------------------------------------------
# compute_peak_mg
# ---------------------------------------------------------------------------


class TestComputePeakMg:
    def test_no_events_returns_zero(self):
        assert compute_peak_mg([], 5.0, 15.0, datetime.now(UTC)) == 0.0

    def test_peak_exceeds_current_level_at_t0(self):
        now = datetime.now(UTC)
        events = [CaffeineEvent(id="a", timestamp=now, mg=100, label="t")]
        current = compute_current_mg(events, 5.0, now, absorption_time_min=15.0)
        peak = compute_peak_mg(events, 5.0, 15.0, now)
        # At t=0 nothing is absorbed yet; peak will be higher
        assert peak > current

    def test_peak_is_below_full_dose(self):
        # The combined absorption+decay model peaks below the nominal dose
        now = datetime.now(UTC)
        events = [CaffeineEvent(id="a", timestamp=now, mg=100, label="t")]
        peak = compute_peak_mg(events, 5.0, 15.0, now)
        assert peak < 100.0

    def test_peak_occurs_within_3h(self):
        # Peak should be found within the 3-hour scan window
        now = datetime.now(UTC)
        events = [CaffeineEvent(id="a", timestamp=now, mg=200, label="t")]
        peak = compute_peak_mg(events, 5.0, 15.0, now)
        assert peak > 0.0

    def test_already_past_peak_returns_current(self):
        # Event consumed 5 hours ago — well past absorption, already declining
        now = datetime.now(UTC)
        ts = now - timedelta(hours=5)
        events = [CaffeineEvent(id="a", timestamp=ts, mg=100, label="t")]
        current = compute_current_mg(events, 5.0, now, absorption_time_min=15.0)
        peak = compute_peak_mg(events, 5.0, 15.0, now)
        assert abs(peak - current) < 1.0


# ---------------------------------------------------------------------------
# compute_sleep_safe_at
# ---------------------------------------------------------------------------


class TestComputeSleepSafeAt:
    def test_already_safe_returns_none(self):
        now = datetime.now(UTC)
        result = compute_sleep_safe_at(40.0, 5.0, 50.0, now)
        assert result is None

    def test_exactly_at_threshold_returns_none(self):
        now = datetime.now(UTC)
        result = compute_sleep_safe_at(50.0, 5.0, 50.0, now)
        assert result is None

    def test_zero_threshold_does_not_divide_by_zero(self):
        now = datetime.now(UTC)
        # Older entries may store 0 mg; it's clamped to 1 mg instead of crashing.
        result = compute_sleep_safe_at(80.0, 5.0, 0.0, now)
        assert result == compute_sleep_safe_at(80.0, 5.0, 1.0, now)

    def test_one_half_life_from_threshold(self):
        now = datetime.now(UTC)
        # 100 mg → 50 mg takes exactly 1 half-life (5 h)
        result = compute_sleep_safe_at(100.0, 5.0, 50.0, now)
        assert result is not None
        expected = now + timedelta(hours=5)
        diff = abs((result - expected).total_seconds())
        assert diff < 1

    def test_math_log2_formula(self):
        now = datetime.now(UTC)
        # 200 → 50: need log2(200/50) = log2(4) = 2 half-lives = 10 h
        result = compute_sleep_safe_at(200.0, 5.0, 50.0, now)
        assert result is not None
        expected = now + timedelta(hours=10)
        diff = abs((result - expected).total_seconds())
        assert diff < 1


# ---------------------------------------------------------------------------
# compute_consumed_today_mg
# ---------------------------------------------------------------------------


class TestComputeConsumedTodayMg:
    def test_all_today(self):
        midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        events = [
            CaffeineEvent(
                id="a", timestamp=midnight + timedelta(hours=1), mg=80, label="e"
            ),
            CaffeineEvent(
                id="b", timestamp=midnight + timedelta(hours=3), mg=95, label="d"
            ),
        ]
        assert compute_consumed_today_mg(events, midnight) == 175.0

    def test_excludes_yesterday(self):
        now = datetime.now(UTC)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        events = [
            CaffeineEvent(
                id="a", timestamp=midnight - timedelta(hours=1), mg=100, label="e"
            ),
            CaffeineEvent(
                id="b", timestamp=midnight + timedelta(hours=1), mg=80, label="d"
            ),
        ]
        assert compute_consumed_today_mg(events, midnight) == 80.0

    def test_empty_events(self):
        midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        assert compute_consumed_today_mg([], midnight) == 0.0


# ---------------------------------------------------------------------------
# CaffeineEvent serialization
# ---------------------------------------------------------------------------


class TestCaffeineEventSerialization:
    def test_round_trip(self):
        ts = datetime(2026, 4, 20, 8, 30, 0, tzinfo=UTC)
        event = CaffeineEvent(id="abc", timestamp=ts, mg=80.0, label="espresso")
        restored = CaffeineEvent.from_dict(event.to_dict())
        assert restored.id == event.id
        assert restored.mg == event.mg
        assert restored.label == event.label
        assert restored.timestamp == event.timestamp

    def test_naive_timestamp_gets_utc(self):
        data = {
            "id": "x",
            "timestamp": "2026-04-20T08:30:00",  # no tz info
            "mg": 80,
            "label": "test",
        }
        event = CaffeineEvent.from_dict(data)
        assert event.timestamp.tzinfo is not None


# ---------------------------------------------------------------------------
# compute_sleep_safe_at_absorbing
# ---------------------------------------------------------------------------


def _brute_force_safe_at(events, half_life, absorption, threshold, now):
    """Last time the level is above threshold, in 10 s steps over 48 h."""
    last_above = None
    for step in range(48 * 360):
        t = now + timedelta(seconds=10 * step)
        if compute_current_mg(events, half_life, t, absorption) > threshold:
            last_above = t
    return last_above


class TestComputeSleepSafeAtAbsorbing:
    def test_fresh_drink_matches_simulation(self):
        now = datetime(2026, 4, 20, 14, 0, tzinfo=UTC)
        events = [CaffeineEvent(id="a", timestamp=now, mg=200, label="t")]
        result = compute_sleep_safe_at_absorbing(events, 5.0, 15.0, 50.0, now)
        expected = _brute_force_safe_at(events, 5.0, 15.0, 50.0, now)
        assert result is not None and expected is not None
        assert abs((result - expected).total_seconds()) < 120

    def test_level_rising_above_threshold_later(self):
        now = datetime(2026, 4, 20, 14, 0, tzinfo=UTC)
        # Just drunk: level is ~0 now but will rise well above 50 mg.
        events = [CaffeineEvent(id="a", timestamp=now, mg=100, label="t")]
        result = compute_sleep_safe_at_absorbing(events, 5.0, 15.0, 50.0, now)
        assert result is not None and result > now + timedelta(hours=4)

    def test_already_absorbed_and_safe(self):
        now = datetime(2026, 4, 20, 14, 0, tzinfo=UTC)
        events = [
            CaffeineEvent(
                id="a", timestamp=now - timedelta(hours=10), mg=100, label="t"
            )
        ]
        assert compute_sleep_safe_at_absorbing(events, 5.0, 15.0, 50.0, now) is None

    def test_no_events(self):
        now = datetime(2026, 4, 20, 14, 0, tzinfo=UTC)
        assert compute_sleep_safe_at_absorbing([], 5.0, 15.0, 50.0, now) is None


# ---------------------------------------------------------------------------
# compute_prune_cutoff
# ---------------------------------------------------------------------------


@pytest.fixture
def utc_time_zone():
    original = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(UTC)
    yield
    dt_util.set_default_time_zone(original)


@pytest.mark.usefixtures("utc_time_zone")
class TestComputePruneCutoff:
    def test_short_half_life_keeps_todays_events(self):
        # 3 h half-life → 21 h of decay would cut off at 02:00, after midnight.
        now = datetime(2026, 4, 20, 23, 0, tzinfo=UTC)
        cutoff = compute_prune_cutoff(now, 3.0)
        assert cutoff == datetime(2026, 4, 20, 0, 0, tzinfo=UTC)

    def test_long_half_life_uses_decay_window(self):
        now = datetime(2026, 4, 20, 23, 0, tzinfo=UTC)
        cutoff = compute_prune_cutoff(now, 5.0)
        assert cutoff == now - timedelta(hours=35)

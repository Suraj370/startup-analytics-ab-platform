"""Tests for the user behavior simulator."""

from src.collector.schemas import EventType
from src.simulator.config import SimulationConfig
from src.simulator.engine import generate_events


# Small config for fast tests
SMALL_CONFIG = SimulationConfig(num_users=200, days=7, seed=42)


class TestGenerateEvents:
    def test_generates_events(self):
        events = generate_events(SMALL_CONFIG)
        assert len(events) > 0

    def test_deterministic_with_same_seed(self):
        events_a = generate_events(SMALL_CONFIG)
        events_b = generate_events(SMALL_CONFIG)
        assert len(events_a) == len(events_b)
        assert [e.event_id for e in events_a] == [e.event_id for e in events_b]

    def test_different_seed_produces_different_events(self):
        config_other = SimulationConfig(num_users=200, days=7, seed=99)
        events_a = generate_events(SMALL_CONFIG)
        events_b = generate_events(config_other)
        # Very unlikely to have identical counts with different seeds
        ids_a = {e.event_id for e in events_a}
        ids_b = {e.event_id for e in events_b}
        assert ids_a != ids_b

    def test_events_sorted_by_timestamp(self):
        events = generate_events(SMALL_CONFIG)
        timestamps = [e.timestamp for e in events]
        assert timestamps == sorted(timestamps)

    def test_all_event_ids_unique(self):
        events = generate_events(SMALL_CONFIG)
        ids = [e.event_id for e in events]
        assert len(ids) == len(set(ids))

    def test_contains_all_funnel_stages(self):
        events = generate_events(SMALL_CONFIG)
        types = {e.event_type for e in events}
        assert EventType.PAGE_VIEW in types
        assert EventType.CLICK in types
        assert EventType.SIGNUP in types
        assert EventType.PURCHASE in types

    def test_funnel_has_natural_dropoff(self):
        events = generate_events(SMALL_CONFIG)
        type_counts = {}
        for e in events:
            type_counts[e.event_type] = type_counts.get(e.event_type, 0) + 1
        # More page views than signups, more signups than purchases
        assert type_counts[EventType.PAGE_VIEW] > type_counts[EventType.SIGNUP]
        assert type_counts[EventType.SIGNUP] > type_counts[EventType.PURCHASE]

    def test_user_ids_follow_pattern(self):
        events = generate_events(SMALL_CONFIG)
        for e in events:
            assert e.user_id.startswith("user_")

    def test_page_view_has_page_property(self):
        events = generate_events(SMALL_CONFIG)
        page_views = [e for e in events if e.event_type == EventType.PAGE_VIEW]
        for pv in page_views:
            assert "page" in pv.properties

    def test_purchase_has_plan_and_amount(self):
        events = generate_events(SMALL_CONFIG)
        purchases = [e for e in events if e.event_type == EventType.PURCHASE]
        assert len(purchases) > 0
        for p in purchases:
            assert "plan" in p.properties
            assert "amount" in p.properties
            assert p.properties["amount"] > 0

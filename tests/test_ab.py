"""Tests for deterministic A/B assignment and experiment definitions."""

import pytest

from src.ab.assignment import assign_variant
from src.ab.experiment import Experiment, Variant, PRICING_PAGE_EXPERIMENT
from src.collector.schemas import EventType
from src.simulator.config import SimulationConfig
from src.simulator.engine import generate_events


class TestExperimentDefinition:
    def test_valid_experiment(self):
        exp = Experiment(
            experiment_id="test",
            name="Test",
            variants=[Variant("a", 0.5), Variant("b", 0.5)],
        )
        assert len(exp.variants) == 2

    def test_weights_must_sum_to_one(self):
        with pytest.raises(ValueError, match="sum to 1.0"):
            Experiment(
                experiment_id="test",
                name="Test",
                variants=[Variant("a", 0.3), Variant("b", 0.3)],
            )

    def test_needs_at_least_two_variants(self):
        with pytest.raises(ValueError, match="at least 2"):
            Experiment(
                experiment_id="test",
                name="Test",
                variants=[Variant("a", 1.0)],
            )

    def test_variant_names_must_be_unique(self):
        with pytest.raises(ValueError, match="unique"):
            Experiment(
                experiment_id="test",
                name="Test",
                variants=[Variant("a", 0.5), Variant("a", 0.5)],
            )

    def test_default_experiment_valid(self):
        assert PRICING_PAGE_EXPERIMENT.experiment_id == "exp_pricing_page_v1"
        assert len(PRICING_PAGE_EXPERIMENT.variants) == 2


class TestAssignment:
    def test_deterministic(self):
        """Same user + experiment always gets the same variant."""
        exp = PRICING_PAGE_EXPERIMENT
        v1 = assign_variant(exp, "user_001")
        v2 = assign_variant(exp, "user_001")
        assert v1 == v2

    def test_different_users_can_get_different_variants(self):
        """With enough users, both variants should appear."""
        exp = PRICING_PAGE_EXPERIMENT
        variants = {assign_variant(exp, f"user_{i}") for i in range(100)}
        assert "control" in variants
        assert "treatment" in variants

    def test_roughly_even_split(self):
        """50/50 experiment should produce roughly even split."""
        exp = PRICING_PAGE_EXPERIMENT
        assignments = [assign_variant(exp, f"user_{i}") for i in range(10000)]
        control_count = assignments.count("control")
        # Should be within 45%-55% for 10k users
        assert 4500 <= control_count <= 5500

    def test_different_experiment_different_assignment(self):
        """Same user in different experiments can get different variants."""
        exp_a = Experiment(
            experiment_id="exp_a", name="A",
            variants=[Variant("c", 0.5), Variant("t", 0.5)],
        )
        exp_b = Experiment(
            experiment_id="exp_b", name="B",
            variants=[Variant("c", 0.5), Variant("t", 0.5)],
        )
        # At least some users should differ across experiments
        differ = False
        for i in range(100):
            uid = f"user_{i}"
            if assign_variant(exp_a, uid) != assign_variant(exp_b, uid):
                differ = True
                break
        assert differ

    def test_returns_valid_variant_name(self):
        exp = PRICING_PAGE_EXPERIMENT
        variant_names = {v.name for v in exp.variants}
        for i in range(100):
            result = assign_variant(exp, f"user_{i}")
            assert result in variant_names

    def test_uneven_split(self):
        """90/10 split should produce roughly 90% in the heavy variant."""
        exp = Experiment(
            experiment_id="uneven", name="Uneven",
            variants=[Variant("heavy", 0.9), Variant("light", 0.1)],
        )
        assignments = [assign_variant(exp, f"user_{i}") for i in range(10000)]
        heavy_count = assignments.count("heavy")
        assert 8500 <= heavy_count <= 9500


class TestSimulatorWithExperiment:
    SMALL_CONFIG = SimulationConfig(num_users=500, days=7, seed=42)

    def test_experiment_events_generated(self):
        events = generate_events(self.SMALL_CONFIG, PRICING_PAGE_EXPERIMENT)
        exp_events = [e for e in events if e.event_type == EventType.EXPERIMENT_ASSIGNMENT]
        assert len(exp_events) == 500  # one per user

    def test_all_users_assigned(self):
        events = generate_events(self.SMALL_CONFIG, PRICING_PAGE_EXPERIMENT)
        exp_events = [e for e in events if e.event_type == EventType.EXPERIMENT_ASSIGNMENT]
        user_ids = {e.user_id for e in exp_events}
        assert len(user_ids) == 500

    def test_experiment_properties_present(self):
        events = generate_events(self.SMALL_CONFIG, PRICING_PAGE_EXPERIMENT)
        exp_events = [e for e in events if e.event_type == EventType.EXPERIMENT_ASSIGNMENT]
        for e in exp_events:
            assert "experiment_id" in e.properties
            assert "variant" in e.properties
            assert e.properties["experiment_id"] == "exp_pricing_page_v1"
            assert e.properties["variant"] in ("control", "treatment")

    def test_treatment_has_higher_purchase_rate(self):
        """Treatment users should convert at a higher rate due to uplift."""
        events = generate_events(self.SMALL_CONFIG, PRICING_PAGE_EXPERIMENT)

        # Build user -> variant mapping
        user_variant = {}
        for e in events:
            if e.event_type == EventType.EXPERIMENT_ASSIGNMENT:
                user_variant[e.user_id] = e.properties["variant"]

        # Count purchases per variant
        purchases = {"control": 0, "treatment": 0}
        users_per = {"control": 0, "treatment": 0}
        for uid, variant in user_variant.items():
            users_per[variant] += 1
            if any(e.user_id == uid and e.event_type == EventType.PURCHASE for e in events):
                purchases[variant] += 1

        control_rate = purchases["control"] / max(users_per["control"], 1)
        treatment_rate = purchases["treatment"] / max(users_per["treatment"], 1)
        # Treatment should have higher or equal purchase rate
        assert treatment_rate >= control_rate

    def test_no_experiment_means_no_assignment_events(self):
        events = generate_events(self.SMALL_CONFIG)
        exp_events = [e for e in events if e.event_type == EventType.EXPERIMENT_ASSIGNMENT]
        assert len(exp_events) == 0

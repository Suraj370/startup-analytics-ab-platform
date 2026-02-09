"""Simulation engine that generates realistic user journey events.

Each simulated user progresses through a funnel:
  page_view(s) -> click(s) -> experiment_assignment -> signup -> onboarding -> purchase

At each stage, the user may drop off based on configured probabilities.
Treatment variant users get a configurable uplift to purchase probability.
All randomness is seeded for full reproducibility.
"""

import hashlib
import random
from datetime import datetime, timedelta, timezone

from src.ab.assignment import assign_variant
from src.ab.experiment import Experiment
from src.collector.schemas import Event, EventType
from src.simulator.config import SimulationConfig


def generate_events(
    config: SimulationConfig | None = None,
    experiment: Experiment | None = None,
) -> list[Event]:
    """Generate a full set of simulated user events.

    If an experiment is provided, each user is deterministically assigned
    to a variant and an experiment_assignment event is emitted.
    Treatment users receive a purchase probability uplift.

    Returns a list of Event objects sorted by timestamp.
    """
    if config is None:
        config = SimulationConfig()

    rng = random.Random(config.seed)
    all_events: list[Event] = []
    # End the simulation window 1 day before now to avoid future timestamps
    # (user journeys can add ~2 hours of in-session time)
    end_time = datetime.now(timezone.utc) - timedelta(days=1)
    start_time = end_time - timedelta(days=config.days)

    for i in range(config.num_users):
        user_id = f"user_{i:05d}"
        user_events = _simulate_user_journey(
            user_id, start_time, config, rng, experiment,
        )
        all_events.extend(user_events)

    all_events.sort(key=lambda e: e.timestamp)
    return all_events


def _simulate_user_journey(
    user_id: str,
    start_time: datetime,
    config: SimulationConfig,
    rng: random.Random,
    experiment: Experiment | None = None,
) -> list[Event]:
    """Simulate a single user's journey through the funnel."""
    events: list[Event] = []
    # Random arrival time within the simulation window
    arrival_offset = timedelta(
        seconds=rng.randint(0, config.days * 86400)
    )
    current_time = start_time + arrival_offset

    # --- Page views ---
    num_pages = rng.randint(config.min_page_views, config.max_page_views)
    for _ in range(num_pages):
        page = rng.choice(config.pages)
        events.append(_make_event(
            user_id, EventType.PAGE_VIEW, current_time, rng,
            properties={"page": page},
        ))
        current_time += timedelta(seconds=rng.randint(5, 120))

    # --- Clicks ---
    num_clicks = rng.randint(config.min_clicks, config.max_clicks)
    for _ in range(num_clicks):
        target = rng.choice(config.click_targets)
        events.append(_make_event(
            user_id, EventType.CLICK, current_time, rng,
            properties={"target": target},
        ))
        current_time += timedelta(seconds=rng.randint(2, 30))

    # --- Experiment assignment (deterministic, before signup gate) ---
    variant = None
    if experiment is not None:
        variant = assign_variant(experiment, user_id)
        current_time += timedelta(seconds=rng.randint(1, 10))
        events.append(_make_event(
            user_id, EventType.EXPERIMENT_ASSIGNMENT, current_time, rng,
            properties={
                "experiment_id": experiment.experiment_id,
                "variant": variant,
            },
        ))

    # --- Signup (funnel gate) ---
    if rng.random() >= config.prob_signup:
        return events  # dropped off before signup

    current_time += timedelta(seconds=rng.randint(10, 300))
    events.append(_make_event(
        user_id, EventType.SIGNUP, current_time, rng,
        properties={"source": "web"},
    ))

    # --- Onboarding (implicit via continued engagement) ---
    if rng.random() >= config.prob_onboarding:
        return events  # dropped off after signup

    # More page views after onboarding
    current_time += timedelta(seconds=rng.randint(60, 3600))
    for _ in range(rng.randint(2, 5)):
        events.append(_make_event(
            user_id, EventType.PAGE_VIEW, current_time, rng,
            properties={"page": "/dashboard"},
        ))
        current_time += timedelta(seconds=rng.randint(10, 180))

    # --- Purchase (funnel gate) ---
    # Treatment variant gets an uplift to simulate a real experiment effect
    purchase_prob = config.prob_purchase
    if variant == "treatment":
        purchase_prob = min(purchase_prob + config.treatment_uplift, 1.0)

    if rng.random() >= purchase_prob:
        return events  # dropped off before purchase

    current_time += timedelta(seconds=rng.randint(30, 600))
    plan_idx = rng.choices(
        range(len(config.plans)),
        weights=config.plan_weights,
        k=1,
    )[0]
    events.append(_make_event(
        user_id, EventType.PURCHASE, current_time, rng,
        properties={
            "plan": config.plans[plan_idx],
            "amount": config.plan_prices[plan_idx],
        },
    ))

    return events


def _make_event(
    user_id: str,
    event_type: EventType,
    timestamp: datetime,
    rng: random.Random,
    properties: dict | None = None,
) -> Event:
    # Deterministic event ID derived from seeded RNG
    event_id = hashlib.md5(rng.randbytes(16)).hexdigest()
    return Event(
        event_id=event_id,
        user_id=user_id,
        event_type=event_type,
        timestamp=timestamp,
        properties=properties or {},
    )

"""CLI entrypoint: generate simulated events and load them into the warehouse.

Usage:
    python -m src.simulator.generate
    python -m src.simulator.generate --users 5000 --days 30
    python -m src.simulator.generate --experiment   # include A/B experiment
"""

import argparse

from src.ab.experiment import PRICING_PAGE_EXPERIMENT
from src.collector.schemas import Event
from src.simulator.config import SimulationConfig
from src.simulator.engine import generate_events
from src.warehouse.db import get_connection, init_db, insert_events


def _events_to_dicts(events: list[Event]) -> list[dict]:
    return [e.model_dump(mode="json") for e in events]


def main(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate simulated analytics events")
    parser.add_argument("--users", type=int, default=2000, help="Number of users")
    parser.add_argument("--days", type=int, default=14, help="Simulation window in days")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--db", type=str, default="data/analytics.duckdb", help="Database path")
    parser.add_argument("--experiment", action="store_true", help="Run with A/B experiment")
    opts = parser.parse_args(args)

    config = SimulationConfig(num_users=opts.users, days=opts.days, seed=opts.seed)
    experiment = PRICING_PAGE_EXPERIMENT if opts.experiment else None

    if experiment:
        print(f"Experiment: {experiment.name} ({experiment.experiment_id})")
        for v in experiment.variants:
            print(f"  {v.name}: {v.weight:.0%} traffic")

    print(f"Generating events for {config.num_users} users over {config.days} days (seed={config.seed})...")
    events = generate_events(config, experiment)
    print(f"Generated {len(events)} events")

    # Summarize funnel
    by_type = {}
    for e in events:
        by_type[e.event_type.value] = by_type.get(e.event_type.value, 0) + 1
    print("Event breakdown:")
    for etype, count in sorted(by_type.items()):
        print(f"  {etype}: {count}")

    # Persist to warehouse
    print(f"\nLoading into warehouse at {opts.db}...")
    conn = get_connection(opts.db)
    init_db(conn)
    inserted, dupes = insert_events(conn, _events_to_dicts(events))
    conn.close()

    print(f"Inserted: {inserted}, Duplicates skipped: {dupes}")
    print("Done.")


if __name__ == "__main__":
    main()

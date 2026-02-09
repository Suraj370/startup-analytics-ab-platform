"""CI validation: verify exported analytics data is complete and sane.

This script is the final gate in CI. It reads the exported dashboard JSON
and asserts structural and logical invariants. If anything is wrong, it
exits non-zero and fails the build.

Usage:
    python ci/validate_analytics.py
    python ci/validate_analytics.py --data src/dashboard/data.json
"""

import argparse
import json
import sys
from pathlib import Path

REQUIRED_TOP_KEYS = {"funnel", "experiments", "event_summary"}
FUNNEL_STEPS = ["page_view", "signup", "purchase"]
ANALYSIS_FIELDS = {
    "absolute_uplift",
    "relative_uplift",
    "p_value",
    "ci_lower",
    "ci_upper",
    "is_significant",
    "decision",
    "reason",
}


def validate(data: dict) -> list[str]:
    """Return a list of validation errors (empty = pass)."""
    errors = []

    # --- Top-level structure ---
    for key in REQUIRED_TOP_KEYS:
        if key not in data:
            errors.append(f"Missing top-level key: {key}")

    if errors:
        return errors  # Can't continue without structure

    # --- Event summary ---
    summary = data["event_summary"]
    if not summary:
        errors.append("event_summary is empty — no events were generated")
    else:
        event_types = {item["event_type"] for item in summary}
        for required in ("page_view", "signup", "purchase"):
            if required not in event_types:
                errors.append(f"event_summary missing required type: {required}")

        for item in summary:
            if item["count"] <= 0:
                errors.append(f"event_summary {item['event_type']} has count <= 0")

    # --- Funnel ---
    funnel = data["funnel"]
    if not funnel:
        errors.append("funnel is empty — no funnel data exported")
    else:
        steps = [s["step"] for s in funnel]
        if steps != FUNNEL_STEPS:
            errors.append(f"Funnel steps {steps} != expected {FUNNEL_STEPS}")

        users = [s["users"] for s in funnel]
        for i in range(1, len(users)):
            if users[i] > users[i - 1]:
                errors.append(
                    f"Funnel not monotonically decreasing: "
                    f"{funnel[i-1]['step']}={users[i-1]} < {funnel[i]['step']}={users[i]}"
                )

        for step in funnel:
            pct = step["conversion_rate_pct"]
            if pct < 0 or pct > 100:
                errors.append(f"Funnel step {step['step']} has invalid rate: {pct}%")

    # --- Experiments ---
    experiments = data["experiments"]
    if not experiments:
        errors.append("experiments is empty — no experiment data exported")
    else:
        for exp in experiments:
            exp_id = exp.get("experiment_id", "UNKNOWN")

            if not exp.get("variants"):
                errors.append(f"Experiment {exp_id} has no variants")
                continue

            variant_names = {v["name"] for v in exp["variants"]}
            if "control" not in variant_names:
                errors.append(f"Experiment {exp_id} missing 'control' variant")
            if "treatment" not in variant_names:
                errors.append(f"Experiment {exp_id} missing 'treatment' variant")

            for v in exp["variants"]:
                if v["users"] <= 0:
                    errors.append(f"Experiment {exp_id} variant {v['name']} has 0 users")

            # Analysis must be present
            analysis = exp.get("analysis")
            if analysis is None:
                errors.append(f"Experiment {exp_id} missing analysis results")
                continue

            missing = ANALYSIS_FIELDS - set(analysis.keys())
            if missing:
                errors.append(f"Experiment {exp_id} analysis missing fields: {missing}")

            if analysis.get("p_value") is not None:
                p = analysis["p_value"]
                if p < 0 or p > 1:
                    errors.append(f"Experiment {exp_id} p-value out of range: {p}")

            if analysis.get("decision") not in ("SHIP", "DO NOT SHIP", "INCONCLUSIVE"):
                errors.append(
                    f"Experiment {exp_id} invalid decision: {analysis.get('decision')}"
                )

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate exported analytics data")
    parser.add_argument(
        "--data",
        default="src/dashboard/data.json",
        help="Path to exported dashboard JSON",
    )
    opts = parser.parse_args()

    path = Path(opts.data)
    if not path.exists():
        print(f"FAIL: {opts.data} not found. Run 'python -m src.analysis.export' first.")
        sys.exit(1)

    data = json.loads(path.read_text())
    errors = validate(data)

    if errors:
        print(f"FAIL: {len(errors)} validation error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    # Print summary on success
    summary = data["event_summary"]
    total_events = sum(item["count"] for item in summary)
    funnel = data["funnel"]
    experiments = data["experiments"]

    print("PASS: Analytics integrity validated")
    print(f"  Events: {total_events:,}")
    print(f"  Funnel: {funnel[0]['users']:,} -> {funnel[-1]['users']:,} users")
    for exp in experiments:
        a = exp["analysis"]
        print(f"  Experiment {exp['experiment_id']}: {a['decision']} (p={a['p_value']:.4f})")


if __name__ == "__main__":
    main()

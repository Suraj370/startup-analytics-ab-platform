"""Deterministic A/B experiment assignment.

Assignment is hash-based: given the same (experiment_id, user_id) pair,
the user always gets the same variant. No randomness involved — the
hash output is mapped to variant buckets based on configured weights.

This guarantees:
- Consistency: same user always sees the same variant
- Reproducibility: assignments can be verified independently
- No coordination: no database lookups needed for assignment
"""

import hashlib

from src.ab.experiment import Experiment


def assign_variant(experiment: Experiment, user_id: str) -> str:
    """Assign a user to a variant deterministically.

    Uses SHA-256 hash of (experiment_id + user_id) to produce a stable
    bucket value in [0.0, 1.0), then maps it to a variant based on
    cumulative traffic weights.
    """
    hash_input = f"{experiment.experiment_id}:{user_id}"
    hash_bytes = hashlib.sha256(hash_input.encode()).digest()
    # Use first 8 bytes as unsigned int, normalize to [0, 1)
    bucket = int.from_bytes(hash_bytes[:8], "big") / (2**64)

    cumulative = 0.0
    for variant in experiment.variants:
        cumulative += variant.weight
        if bucket < cumulative:
            return variant.name

    # Fallback to last variant (handles floating point edge cases)
    return experiment.variants[-1].name

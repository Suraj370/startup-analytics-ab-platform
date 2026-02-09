"""Simulation parameters for realistic user behavior.

These numbers model a typical B2B SaaS signup funnel:
  landing_page -> signup -> onboarding -> purchase

Drop-off rates are calibrated to produce enough conversions
for statistical analysis while remaining realistic.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SimulationConfig:
    num_users: int = 2000
    # Number of days the simulation spans
    days: int = 14
    # Random seed for reproducibility
    seed: int = 42

    # Funnel step probabilities (conditional on reaching previous step)
    prob_signup: float = 0.30        # 30% of visitors sign up
    prob_onboarding: float = 0.70    # 70% of signups complete onboarding
    prob_purchase: float = 0.15      # 15% of onboarded users purchase
    treatment_uplift: float = 0.08   # +8pp purchase lift for treatment variant

    # Browsing behavior
    min_page_views: int = 1
    max_page_views: int = 8
    min_clicks: int = 0
    max_clicks: int = 5

    # Pages users can visit
    pages: tuple[str, ...] = (
        "/",
        "/features",
        "/pricing",
        "/docs",
        "/blog",
        "/about",
    )

    # Clickable elements
    click_targets: tuple[str, ...] = (
        "cta_hero",
        "cta_pricing",
        "nav_features",
        "nav_docs",
        "footer_signup",
    )

    # Purchase plans
    plans: tuple[str, ...] = ("starter", "pro", "enterprise")
    plan_prices: tuple[float, ...] = (29.0, 99.0, 299.0)
    # Weighted toward cheaper plans
    plan_weights: tuple[float, ...] = (0.6, 0.3, 0.1)

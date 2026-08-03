"""
Phase 5 - Plan & Build
services/plan.py - single source of truth for the 90-day roadmap and team
recommender.
"""

from models.schemas import (
    RoadmapMilestone,
    TeamRole,
    RolePriority,
    PlanRequest,
    PlanResponse,
)

# ---- Baseline roles every idea needs, regardless of vertical ----
BASE_ROLES = [
    TeamRole(
        role="Founding Engineer",
        priority=RolePriority.CRITICAL,
        reason="You need a working MVP before anything else in this roadmap matters.",
        skills=["Full-stack", "Fast shipping over polish", "Comfortable with ambiguity"],
    ),
]

# ---- Vertical -> extra roles, keyed by keyword match on idea_summary/vertical ----
VERTICAL_ROLE_RULES = {
    "marketplace": TeamRole(
        role="Community/Ops Lead",
        priority=RolePriority.CRITICAL,
        reason="Marketplaces live or die on supply-side liquidity — someone has to hand-hold early sellers/providers.",
        skills=["Cold outreach", "Community management", "Operational hustle"],
    ),
    "fintech": TeamRole(
        role="Compliance Advisor",
        priority=RolePriority.IMPORTANT,
        reason="Fintech regulatory exposure compounds fast — cheaper to bring in early than retrofit.",
        skills=["Financial regulation", "KYC/AML familiarity"],
    ),
    "devtool": TeamRole(
        role="Developer Advocate",
        priority=RolePriority.IMPORTANT,
        reason="Devtools are won on trust and docs quality, not ads — you need someone who lives in the community.",
        skills=["Technical writing", "Open source presence", "Public speaking/content"],
    ),
    "consumer_social": TeamRole(
        role="Growth/Design Hybrid",
        priority=RolePriority.CRITICAL,
        reason="Consumer social lives or dies on retention loops and visual polish from day one.",
        skills=["Product design", "Growth loops", "Data-informed iteration"],
    ),
}


def _detect_vertical(request: PlanRequest, idea_summary: str) -> str | None:
    if request.vertical:
        return request.vertical.lower()
    summary_lower = idea_summary.lower()
    for key in VERTICAL_ROLE_RULES:
        if key in summary_lower:
            return key
    return None


def recommend_team(request: PlanRequest, idea_summary: str) -> list[TeamRole]:
    roles = list(BASE_ROLES)
    matched_vertical = _detect_vertical(request, idea_summary)
    if matched_vertical and matched_vertical in VERTICAL_ROLE_RULES:
        roles.append(VERTICAL_ROLE_RULES[matched_vertical])
    return roles


def generate_roadmap(request: PlanRequest, idea_summary: str, top_risks: list[str]) -> list[RoadmapMilestone]:
    matched_vertical = _detect_vertical(request, idea_summary)

    # Day 1-30: Foundation
    foundation_tasks = [
        "Conduct 10 problem-interview calls with target users.",
        "Scope absolute minimum feature set — cut everything optional.",
        "Build basic core flow end-to-end.",
    ]
    if matched_vertical == "fintech":
        foundation_tasks.append("Confirm legal/compliance boundary for early pilot.")
    elif matched_vertical == "marketplace":
        foundation_tasks.append("Hand-onboard first 5 supply-side users manually.")

    # Day 31-60: Validation / Pilot
    pilot_tasks = [
        "Launch working MVP to initial cohort of 20-50 target users.",
        "Track core activation metric (e.g. completed first value action).",
        "Iterate on feedback weekly — fix high-friction drop-offs.",
    ]

    # Day 61-90: Growth
    growth_tasks = [
        "Establish one repeatable acquisition channel.",
        "Test baseline pricing / revenue model with real users.",
        "Formulate post-MVP hiring or fundraising plan if metrics hold.",
    ]

    return [
        RoadmapMilestone(
            day_range="Day 1-30",
            block_title="Foundation",
            tasks=foundation_tasks,
            deliverable="Scope defined + core flow built + initial user feedback",
            risk_flags=top_risks[:2],
        ),
        RoadmapMilestone(
            day_range="Day 31-60",
            block_title="Validation / Pilot",
            tasks=pilot_tasks,
            deliverable="Working MVP live with active initial users",
            risk_flags=top_risks[2:3],
        ),
        RoadmapMilestone(
            day_range="Day 61-90",
            block_title="Growth",
            tasks=growth_tasks,
            deliverable="One proven acquisition channel + validated revenue model",
        ),
    ]


def generate_plan(request: PlanRequest, idea_summary: str, top_risks: list[str]) -> PlanResponse:
    roadmap = generate_roadmap(request, idea_summary, top_risks)
    team = recommend_team(request, idea_summary)

    revenue_options = ["Subscription (SaaS)", "Usage-based", "Marketplace take rate", "Freemium + upsell"]

    solo_note = None
    if len(team) == 1:
        solo_note = "This idea's roadmap is realistically solo-buildable through MVP (Day 30). Revisit team needs after launch."

    return PlanResponse(
        roadmap=roadmap,
        team=team,
        revenue_model_options=revenue_options,
        solo_founder_note=solo_note,
    )

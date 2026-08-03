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

# ---- Risk keyword -> roadmap task injected into the relevant block ----
RISK_TASK_MAP = {
    "market": "Run 15 more customer discovery calls targeting the specific segment flagged as unverified",
    "moat": "Ship one feature competitors structurally cannot copy quickly (data, network, or workflow lock-in)",
    "unit economics": "Build a live CAC/LTV tracker before spending on any paid acquisition",
    "team": "Close the most critical role gap before Day 30 — do not build solo past MVP if flagged",
    "timing": "Validate urgency with 5 prospects willing to pre-pay or sign LOI before Day 45",
    "gtm": "Test the top 2 acquisition channels with a $500 spend cap each before committing budget",
}


def _match_vertical_role(request: PlanRequest, idea_summary: str) -> TeamRole | None:
    text = f"{request.vertical or ''} {idea_summary}".lower()
    for keyword, role in VERTICAL_ROLE_RULES.items():
        if keyword.replace("_", " ") in text or keyword in text:
            return role
    return None


def _risk_tasks_for_block(top_risks: list[str]) -> list[str]:
    tasks = []
    for risk in top_risks:
        risk_lower = risk.lower()
        for keyword, task in RISK_TASK_MAP.items():
            if keyword in risk_lower:
                tasks.append(task)
                break
    return tasks


def recommend_team(request: PlanRequest, idea_summary: str) -> list[TeamRole]:
    team = list(BASE_ROLES)
    vertical_role = _match_vertical_role(request, idea_summary)
    if vertical_role:
        team.append(vertical_role)
    return team


def generate_roadmap(request: PlanRequest, idea_summary: str, top_risks: list[str]) -> list[RoadmapMilestone]:
    risk_tasks = _risk_tasks_for_block(top_risks)

    mvp_tasks = [
        "Scope MVP to the single narrowest workflow that proves the core problem-solution fit",
        "Ship to 10 hand-picked users, not a public launch",
    ] + risk_tasks[:2]

    launch_tasks = [
        "Public launch on the channel with highest signal from Phase 2 data (Reddit/HN/PH)",
        "Instrument activation and Day-7 retention before spending on acquisition",
    ] + risk_tasks[2:3]

    growth_tasks = [
        "Double down on the single channel with best CAC from the launch block",
        "Formalize the revenue model that showed real willingness-to-pay",
    ]

    return [
        RoadmapMilestone(
            day_range="Day 1-30",
            block_title="MVP Build",
            tasks=mvp_tasks,
            deliverable="Working MVP validated by 10 real users, not friends/family",
            risk_flags=top_risks[:2],
        ),
        RoadmapMilestone(
            day_range="Day 31-60",
            block_title="Launch",
            tasks=launch_tasks,
            deliverable="Public launch executed, activation/retention metrics instrumented",
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

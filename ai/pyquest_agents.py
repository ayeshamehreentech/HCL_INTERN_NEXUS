"""Deterministic curriculum specialist for the PyQuest coding lab.

This module is deliberately provider- and database-agnostic.  The UI can load
durable attempt counts from Supabase, pass those plain values into
``plan_next_skill``, and render the returned plan.  Keeping planning pure makes
the unlock rules reproducible and easy to test.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CurriculumWorld:
    """A themed area on the learner's map and its entry requirement."""

    key: str
    title: str
    scenario: str
    description: str
    unlock_at_total: int


@dataclass(frozen=True)
class CurriculumStage:
    """One mastery skill within a curriculum world."""

    key: str
    title: str
    concept: str
    world_key: str
    scenario_id: str
    required_verified_answers: int
    unlock_at_total: int


@dataclass(frozen=True)
class CurriculumPlan:
    """A serialisable decision made by the syllabus architect."""

    stage: CurriculumStage
    world: CurriculumWorld
    verified_for_stage: int
    total_verified: int
    is_world_unlocked: bool
    is_complete: bool
    reason: str


PYQUEST_WORLDS: tuple[CurriculumWorld, ...] = (
    CurriculumWorld("village", "Python Village", "SHOPPING_CART", "Speak to the computer with print and input.", 0),
    CurriculumWorld("mall", "Mall Mission", "FUEL_STATION", "Store useful values and calculate with them.", 6),
    CurriculumWorld("castle", "Castle Kingdom", "CASTLE_GATE", "Make safe decisions with conditions.", 9),
    CurriculumWorld("forest", "Loop Forest", "TREASURE_COLLECTION", "Repeat small actions with control.", 12),
    CurriculumWorld("factory", "Function Factory", "ROBOT_REPAIR", "Package reusable ideas into functions.", 15),
)


PYQUEST_STAGES: tuple[CurriculumStage, ...] = (
    CurriculumStage("print", "First Words", "print()", "village", "SHOPPING_CART", 3, 0),
    CurriculumStage("input", "Airport Check-in", "input()", "village", "LOCKED_DOOR", 3, 3),
    CurriculumStage("variables", "Mall Mission", "variables", "mall", "FUEL_STATION", 3, 6),
    CurriculumStage("conditions", "Castle Gate", "if / else", "castle", "CASTLE_GATE", 3, 9),
    CurriculumStage("loops", "Fuel Station", "for loops", "forest", "TREASURE_COLLECTION", 3, 12),
    CurriculumStage("functions", "Robot Repair", "functions", "factory", "ROBOT_REPAIR", 3, 15),
)


_WORLDS_BY_KEY = {world.key: world for world in PYQUEST_WORLDS}


def _count(value: object) -> int:
    """Normalise a Supabase result without allowing negative counts."""
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def plan_next_skill(
    total_verified: int,
    verified_by_category: Mapping[str, int] | None = None,
) -> CurriculumPlan:
    """Choose the first not-yet-mastered skill in the fixed learning order.

    ``total_verified`` is the number of distinct passing questions and
    ``verified_by_category`` maps a stage key (for example ``"print"``) to its
    distinct passing count.  A later stage is never selected before all earlier
    stages have met their mastery requirement, even when old data is incomplete.
    """
    category_counts = verified_by_category or {}
    total = _count(total_verified)

    for stage in PYQUEST_STAGES:
        verified = _count(category_counts.get(stage.key, 0))
        previous_complete = all(
            _count(category_counts.get(previous.key, 0)) >= previous.required_verified_answers
            for previous in PYQUEST_STAGES[: PYQUEST_STAGES.index(stage)]
        )
        world = _WORLDS_BY_KEY[stage.world_key]
        world_unlocked = total >= world.unlock_at_total and previous_complete
        if verified < stage.required_verified_answers:
            reason = (
                "Complete {} more verified challenge{} in {}."
                .format(stage.required_verified_answers - verified,
                        "" if stage.required_verified_answers - verified == 1 else "s",
                        stage.concept)
            )
            if not world_unlocked:
                reason = "Finish the earlier skill before entering {}.".format(world.title)
            return CurriculumPlan(stage, world, verified, total, world_unlocked, False, reason)

    final_stage = PYQUEST_STAGES[-1]
    final_world = _WORLDS_BY_KEY[final_stage.world_key]
    return CurriculumPlan(
        final_stage, final_world, final_stage.required_verified_answers, total,
        True, True, "All core PyQuest skills are mastered. Continue with generated practice missions.",
    )

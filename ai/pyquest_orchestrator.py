"""Coordinator for the specialised, deterministic PyQuest agents.

This module contains no Streamlit, database, or provider calls.  The portal
loads durable Supabase counts, passes plain values here, then decides how to
render or persist the returned decision.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

from ai.pyquest_agents import CurriculumPlan, plan_next_skill
from ai.pyquest_teaching import teaching_step


@dataclass(frozen=True)
class PyQuestDecision:
    """Combined curriculum and teaching response for one learner turn."""

    plan: CurriculumPlan
    teaching: dict

    def to_dict(self) -> dict:
        return {"plan": asdict(self.plan), "teaching": self.teaching}


def coordinate_learning_turn(
    *,
    total_verified: int,
    verified_by_category: Mapping[str, int],
    consecutive_failures: int = 0,
    feedback: str = "",
) -> PyQuestDecision:
    """Route progress through Syllabus Architect then Storyteller/Camp agent."""

    plan = plan_next_skill(total_verified, verified_by_category)
    teaching = teaching_step(plan.stage.key, consecutive_failures, feedback)
    return PyQuestDecision(plan=plan, teaching=teaching)


__all__ = ["PyQuestDecision", "coordinate_learning_turn"]

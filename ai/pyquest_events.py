"""Safe, predefined events that Python may send to the PyQuest visual layer."""
from __future__ import annotations

ALLOWED_EVENTS = frozenset({
    "CASTLE_GATE_LOCKED", "CASTLE_GATE_SHAKE", "CASTLE_GATE_UNLOCKED",
    "CASTLE_GATE_OPEN", "TREASURE_REVEALED", "CAR_START", "CAR_MOVE",
    "CAR_STOP", "FUEL_LOW", "FUEL_FILLED", "CAR_REACHES_STATION", "LIGHT_RED", "LIGHT_YELLOW",
    "LIGHT_GREEN", "CAR_WAIT", "ROBOT_BROKEN", "ROBOT_REPAIRING",
    "ROBOT_FIXED", "ROBOT_CELEBRATION", "CHEST_LOCKED", "CHEST_OPEN",
    "COIN_COLLECTED", "TREASURE_FOUND", "DOOR_LOCKED", "WRONG_CODE",
    "KEY_FOUND", "DOOR_UNLOCKED", "DOOR_OPEN", "MISSION_COMPLETE", "LEVEL_UP",
})


def validated_events(events: list[str]) -> list[str]:
    """Reject unknown event names before the browser sees them."""
    return [event for event in events if event in ALLOWED_EVENTS]


def outcome_events(scenario: str, passed: bool, level_up: bool = False) -> list[str]:
    """Map a validated Python outcome to fixed visual events; no LLM controls this."""
    scenario = (scenario or "").upper()
    if not passed:
        return validated_events(["CASTLE_GATE_SHAKE" if scenario == "CASTLE_GATE" else "WRONG_CODE"])
    mapping = {
        "CASTLE_GATE": ["CASTLE_GATE_UNLOCKED", "CASTLE_GATE_OPEN", "TREASURE_REVEALED"],
        "FUEL_STATION": ["CAR_START", "CAR_MOVE", "CAR_STOP", "CAR_REACHES_STATION", "FUEL_FILLED"],
        "TRAFFIC_SIGNAL": ["LIGHT_GREEN", "CAR_MOVE"],
        "ROBOT_REPAIR": ["ROBOT_REPAIRING", "ROBOT_FIXED", "ROBOT_CELEBRATION"],
        "TREASURE_COLLECTION": ["CHEST_OPEN", "COIN_COLLECTED", "TREASURE_FOUND"],
        "LOCKED_DOOR": ["KEY_FOUND", "DOOR_UNLOCKED", "DOOR_OPEN"],
    }
    events = mapping.get(scenario, ["COIN_COLLECTED"])
    events += ["MISSION_COMPLETE"]
    if level_up:
        events.append("LEVEL_UP")
    return validated_events(events)

"""Data model for a trip stop plus the single source of truth for validation rules.

Every part of the app (interactive prompts, JSON loading, CSV import) uses the
limits and the ``Stop.from_dict`` validator defined here, so rules never drift.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass

CATEGORIES = ("fuel", "food", "hotel", "sightseeing", "rest", "other")
STATUSES = ("planned", "visited", "skipped")

NAME_LEN = (2, 50)
DIST_RANGE = (0.1, 5000.0)       # km from the previous stop
TRAVEL_RANGE = (1, 10000)        # minutes of driving
STAY_RANGE = (0, 2880)           # minutes spent at the stop (max 48 h)
PRIORITY_RANGE = (1, 5)          # 5 = must-do
NOTES_MAX = 200


def _number(data: dict, key: str, whole: bool, lo, hi):
    """Read ``data[key]`` as a number inside [lo, hi] or raise ValueError."""
    raw = data.get(key)
    text = "" if raw is None else str(raw).strip()
    if text == "":
        raise ValueError(f"{key} is missing")
    try:
        value = float(text)
    except ValueError:
        raise ValueError(f"{key} '{text}' is not a number") from None
    if not math.isfinite(value):
        raise ValueError(f"{key} '{text}' is not a valid number")
    if whole:
        if value != int(value):
            raise ValueError(f"{key} '{text}' must be a whole number")
        value = int(value)
    if not lo <= value <= hi:
        raise ValueError(f"{key} {text} is out of range ({lo} to {hi})")
    return value


@dataclass
class Stop:
    """One stop on the road trip. ``distance_km`` is measured from the previous stop."""

    id: int
    name: str
    category: str
    distance_km: float
    travel_time_min: int
    stay_time_min: int = 0
    priority: int = 3
    status: str = "planned"
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def speed_kmh(self) -> float:
        """Average speed implied by the distance and travel time of this leg."""
        return self.distance_km / (self.travel_time_min / 60)

    @classmethod
    def from_dict(cls, data: dict) -> "Stop":
        """Build a validated Stop from a dict (JSON record or CSV row).

        Raises ValueError with a human-readable message on the first problem.
        """
        name = re.sub(r"\s+", " ", str(data.get("name") or "")).strip()
        if not NAME_LEN[0] <= len(name) <= NAME_LEN[1]:
            raise ValueError(f"name must be {NAME_LEN[0]}-{NAME_LEN[1]} characters")
        if not re.search(r"[A-Za-z0-9]", name):
            raise ValueError("name must contain a letter or digit")

        category = str(data.get("category") or "").strip().lower()
        if category not in CATEGORIES:
            raise ValueError(f"category '{category}' must be one of {', '.join(CATEGORIES)}")

        status = str(data.get("status") or "planned").strip().lower()
        if status not in STATUSES:
            raise ValueError(f"status '{status}' must be one of {', '.join(STATUSES)}")

        notes = str(data.get("notes") or "").strip()
        if len(notes) > NOTES_MAX:
            raise ValueError(f"notes longer than {NOTES_MAX} characters")

        try:
            stop_id = int(data.get("id") or 0)
        except (TypeError, ValueError):
            stop_id = 0

        return cls(
            id=stop_id,
            name=name,
            category=category,
            distance_km=float(_number(data, "distance_km", False, *DIST_RANGE)),
            travel_time_min=_number(data, "travel_time_min", True, *TRAVEL_RANGE),
            stay_time_min=_number(data, "stay_time_min", True, *STAY_RANGE),
            priority=_number(data, "priority", True, *PRIORITY_RANGE),
            status=status,
            notes=notes,
        )

"""Core business logic: add/arrange stops, travel-time estimates, totals and ETAs."""
from __future__ import annotations

from datetime import datetime, timedelta

from models import CATEGORIES, Stop


def estimate_travel_minutes(distance_km: float, speed_kmh: float = 60) -> int:
    """time = distance / speed * 60, never below 1 minute."""
    return max(1, round(distance_km / speed_kmh * 60))


def next_id(stops) -> int:
    return max((s.id for s in stops), default=0) + 1


def find_duplicate(stops, name: str, ignore_id=None):
    """Return an existing stop with the same name (case-insensitive) or None."""
    wanted = name.strip().lower()
    for s in stops:
        if s.name.lower() == wanted and s.id != ignore_id:
            return s
    return None


def add_stop(stops: list, stop: Stop) -> Stop:
    if find_duplicate(stops, stop.name):
        raise ValueError(f"A stop named '{stop.name}' already exists.")
    stop.id = next_id(stops)
    stops.append(stop)
    return stop


def active_stops(stops):
    """Stops that are still part of the trip (skipped ones are excluded from totals)."""
    return [s for s in stops if s.status != "skipped"]


def sort_stops(stops, mode: str) -> list:
    """Return a re-ordered copy. Modes: priority, distance, category."""
    if mode == "priority":      # highest priority first, ties keep current order
        return sorted(stops, key=lambda s: -s.priority)
    if mode == "distance":      # shortest leg first
        return sorted(stops, key=lambda s: s.distance_km)
    if mode == "category":      # grouped in the CATEGORIES order
        return sorted(stops, key=lambda s: CATEGORIES.index(s.category))
    raise ValueError(f"Unknown sort mode '{mode}'")


def move_stop(stops: list, index: int, direction: int) -> int:
    """Move stops[index] up (-1) or down (+1). Returns the new index."""
    new = index + direction
    if not 0 <= new < len(stops):
        raise ValueError("Cannot move the stop any further in that direction.")
    stops[index], stops[new] = stops[new], stops[index]
    return new


def trip_totals(stops) -> dict:
    act = active_stops(stops)
    distance = sum(s.distance_km for s in act)
    drive = sum(s.travel_time_min for s in act)
    stay = sum(s.stay_time_min for s in act)
    return {"stops": len(act), "distance_km": distance, "drive_min": drive,
            "stay_min": stay, "total_min": drive + stay}


def compute_etas(stops, start: datetime):
    """Yield (stop, arrival, departure) for every active stop, starting at ``start``."""
    clock, result = start, []
    for s in active_stops(stops):
        arrive = clock + timedelta(minutes=s.travel_time_min)
        depart = arrive + timedelta(minutes=s.stay_time_min)
        result.append((s, arrive, depart))
        clock = depart
    return result


def distance_gaps(stops, limit_km: float, kinds=("fuel",)):
    """Find places where more than ``limit_km`` is driven without a stop of ``kinds``.

    Returns a list of (stop, km_since_last) - one entry per offending stretch.
    """
    gaps, run, flagged = [], 0.0, False
    for s in active_stops(stops):
        run += s.distance_km
        if run > limit_km and not flagged:
            gaps.append((s, run))
            flagged = True
        if s.category in kinds:
            run, flagged = 0.0, False
    return gaps


def estimate_fuel(distance_km: float, mileage_km_per_l: float, price_per_l: float):
    """Return (litres, cost) for a distance at the given mileage and fuel price."""
    litres = distance_km / mileage_km_per_l
    return litres, litres * price_per_l


def day_plan(stops, start: datetime) -> list:
    """Split the active route into driving days. A hotel stop ends a day.

    Returns a list of dicts: {day, items[(stop, arrive, depart)], km, drive_min, stay_min}.
    """
    groups, current = [], []
    for item in compute_etas(stops, start):
        current.append(item)
        if item[0].category == "hotel":
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return [{"day": i, "items": g,
             "km": sum(s.distance_km for s, _, _ in g),
             "drive_min": sum(s.travel_time_min for s, _, _ in g),
             "stay_min": sum(s.stay_time_min for s, _, _ in g)}
            for i, g in enumerate(groups, 1)]

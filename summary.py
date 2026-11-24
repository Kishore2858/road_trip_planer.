"""Executive summary: totals, averages, status/category breakdown, trends, warnings."""
from __future__ import annotations

from collections import Counter

import planner
import ui
from models import CATEGORIES, STATUSES

# Warning thresholds
MAX_LEG_KM = 300
MAX_DAILY_DRIVE_MIN = 8 * 60
MAX_FUEL_GAP_KM = 250
MAX_SPEED_KMH = 130
MIN_SPEED_KMH = 15


def build_summary(stops, settings=None) -> dict:
    act = planner.active_stops(stops)
    totals = planner.trip_totals(stops)
    status_counts = Counter(s.status for s in stops)
    cat_counts = Counter(s.category for s in stops)
    drive_h = totals["drive_min"] / 60
    fuel = None
    if settings:
        litres, cost = planner.estimate_fuel(totals["distance_km"], settings["mileage_km_per_l"],
                                             settings["fuel_price_per_l"])
        fuel = {"litres": litres, "cost": cost, "mileage": settings["mileage_km_per_l"],
                "price": settings["fuel_price_per_l"]}
    return {
        "fuel": fuel,
        **totals,
        "all_stops": len(stops),
        "status_counts": {k: status_counts.get(k, 0) for k in STATUSES},
        "category_counts": {k: cat_counts.get(k, 0) for k in CATEGORIES if cat_counts.get(k)},
        "pct_complete": (status_counts.get("visited", 0) / len(act) * 100) if act else 0.0,
        "avg_leg_km": totals["distance_km"] / len(act) if act else 0.0,
        "avg_leg_min": totals["drive_min"] / len(act) if act else 0.0,
        "avg_speed": totals["distance_km"] / drive_h if drive_h else 0.0,
        "longest": max(act, key=lambda s: s.distance_km, default=None),
        "shortest": min(act, key=lambda s: s.distance_km, default=None),
        "busiest_category": cat_counts.most_common(1)[0] if cat_counts else None,
    }


def collect_warnings(stops) -> list:
    """Threshold warnings: long legs, long driving days, fuel gaps, odd speeds, skipped must-dos."""
    warnings = []
    act = planner.active_stops(stops)
    for s in act:
        if s.distance_km > MAX_LEG_KM:
            warnings.append(f"Long leg: '{s.name}' is {s.distance_km:.0f} km (limit {MAX_LEG_KM} km).")
        if s.speed_kmh > MAX_SPEED_KMH:
            warnings.append(f"Unrealistic speed: '{s.name}' implies {s.speed_kmh:.0f} km/h - check the travel time.")
        elif s.distance_km >= 20 and s.speed_kmh < MIN_SPEED_KMH:
            warnings.append(f"Very slow leg: '{s.name}' implies {s.speed_kmh:.0f} km/h - check the travel time.")

    day, drive = 1, 0
    for s in act:                      # a hotel stop ends the driving day
        drive += s.travel_time_min
        if s.category == "hotel":
            if drive > MAX_DAILY_DRIVE_MIN:
                warnings.append(f"Day {day} has {ui.fmt_minutes(drive)} of driving (limit {ui.fmt_minutes(MAX_DAILY_DRIVE_MIN)}).")
            day, drive = day + 1, 0
    if drive > MAX_DAILY_DRIVE_MIN:
        warnings.append(f"Day {day} has {ui.fmt_minutes(drive)} of driving (limit {ui.fmt_minutes(MAX_DAILY_DRIVE_MIN)}).")

    for s, run in planner.distance_gaps(stops, MAX_FUEL_GAP_KM, ("fuel",)):
        warnings.append(f"No fuel stop for {run:.0f} km by '{s.name}' (limit {MAX_FUEL_GAP_KM} km).")
    for s in stops:
        if s.status == "skipped" and s.priority == 5:
            warnings.append(f"Top-priority stop '{s.name}' was skipped.")
    return warnings


def summary_lines(stats: dict) -> list:
    """Plain-text summary used by the terminal, TXT and Markdown exports."""
    if stats["all_stops"] == 0:
        return ["No stops recorded yet."]
    sc = stats["status_counts"]
    lines = [
        f"Stops in trip (excl. skipped): {stats['stops']} of {stats['all_stops']}",
        f"Total distance:      {stats['distance_km']:.1f} km",
        f"Total driving time:  {ui.fmt_minutes(stats['drive_min'])}",
        f"Total stay time:     {ui.fmt_minutes(stats['stay_min'])}",
        f"Total trip time:     {ui.fmt_minutes(stats['total_min'])}",
        f"Average leg:         {stats['avg_leg_km']:.1f} km / {ui.fmt_minutes(stats['avg_leg_min'])}",
        f"Average speed:       {stats['avg_speed']:.1f} km/h",
        f"Status:              planned {sc['planned']} | visited {sc['visited']} | skipped {sc['skipped']}",
        f"Progress:            {stats['pct_complete']:.0f}% of active stops visited",
    ]
    if stats.get("fuel"):
        f = stats["fuel"]
        lines.append(f"Estimated fuel:      {f['litres']:.1f} L, cost {f['cost']:,.0f} "
                     f"({f['mileage']:g} km/L at {f['price']:g}/L)")
    if stats["longest"]:
        lines.append(f"Longest leg:         {stats['longest'].name} ({stats['longest'].distance_km:.1f} km)")
        lines.append(f"Shortest leg:        {stats['shortest'].name} ({stats['shortest'].distance_km:.1f} km)")
    if stats["busiest_category"]:
        cat, n = stats["busiest_category"]
        lines.append(f"Busiest category:    {cat} ({n} stops)")
    lines.append("")
    lines.append("Stops by category:")
    peak = max(stats["category_counts"].values())
    for cat, n in stats["category_counts"].items():
        lines.append(f"  {cat:<12} {ui.bar(n, peak):<20} {n}")
    return lines

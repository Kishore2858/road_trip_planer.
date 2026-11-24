"""Keyword and category based filtering of stored stops."""
from __future__ import annotations


def filter_stops(stops, keyword=None, category=None, status=None, min_km=None, max_km=None):
    """Return stops matching ALL supplied filters (None means 'do not filter')."""
    kw = keyword.strip().lower() if keyword else None
    out = []
    for s in stops:
        if kw and kw not in s.name.lower() and kw not in s.notes.lower():
            continue
        if category and s.category != category:
            continue
        if status and s.status != status:
            continue
        if min_km is not None and s.distance_km < min_km:
            continue
        if max_km is not None and s.distance_km > max_km:
            continue
        out.append(s)
    return out


def sort_results(stops, order: str):
    """Order search results: route (unchanged), distance, priority (high first) or name."""
    if order == "distance":
        return sorted(stops, key=lambda s: s.distance_km)
    if order == "priority":
        return sorted(stops, key=lambda s: -s.priority)
    if order == "name":
        return sorted(stops, key=lambda s: s.name.lower())
    return list(stops)

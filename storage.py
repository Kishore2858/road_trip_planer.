"""JSON persistence with defensive loading and crash-safe (atomic) saving."""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from models import Stop

DEFAULT_SETTINGS = {"avg_speed_kmh": 60, "start_time": "08:00", "mileage_km_per_l": 15, "fuel_price_per_l": 100}
# numeric settings and their allowed (min, max)
NUMERIC_SETTINGS = {"avg_speed_kmh": (10, 150), "mileage_km_per_l": (1, 60), "fuel_price_per_l": (1, 1000)}
SCHEMA_VERSION = 1


def _clean_settings(raw) -> dict:
    settings = dict(DEFAULT_SETTINGS)
    if isinstance(raw, dict):
        for key, (lo, hi) in NUMERIC_SETTINGS.items():
            val = raw.get(key)
            if isinstance(val, (int, float)) and not isinstance(val, bool) and lo <= val <= hi:
                settings[key] = val
        start = raw.get("start_time")
        if isinstance(start, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", start):
            settings["start_time"] = start
    return settings


def save(path, stops, settings=None) -> None:
    """Write state to ``path`` atomically: temp file first, then rename."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": SCHEMA_VERSION,
        "settings": _clean_settings(settings),
        "stops": [s.to_dict() for s in stops],
    }
    if path.exists():                       # keep the previous version as stops.json.bak
        try:
            shutil.copy2(path, path.with_name(path.name + ".bak"))
        except OSError:
            pass
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _recover(path: Path, reason: str, messages: list):
    """Move an unreadable file aside, start fresh, and tell the user."""
    backup = path.with_name(f"{path.stem}.corrupt{path.suffix}")
    try:
        os.replace(path, backup)
        messages.append(("warn", f"Data file was unreadable ({reason}). Backed up as {backup.name}; starting fresh."))
    except OSError:
        messages.append(("warn", f"Data file was unreadable ({reason}); starting fresh."))
    settings = dict(DEFAULT_SETTINGS)
    save(path, [], settings)
    return [], settings, messages


def load(path):
    """Return ``(stops, settings, messages)``; never raises for bad/missing files.

    ``messages`` is a list of ``(level, text)`` for the UI to display.
    """
    path = Path(path)
    messages: list = []
    if not path.exists():
        settings = dict(DEFAULT_SETTINGS)
        save(path, [], settings)
        messages.append(("info", f"No data file found - created a new one at {path.name}."))
        return [], settings, messages

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        return _recover(path, type(exc).__name__, messages)

    if isinstance(raw, list):
        records, settings = raw, dict(DEFAULT_SETTINGS)
    elif isinstance(raw, dict) and isinstance(raw.get("stops"), list):
        records, settings = raw["stops"], _clean_settings(raw.get("settings"))
    else:
        return _recover(path, "unexpected structure", messages)

    stops, names, ids = [], set(), set()
    for i, rec in enumerate(records, 1):
        try:
            if not isinstance(rec, dict):
                raise ValueError("record is not an object")
            stop = Stop.from_dict(rec)
            if stop.name.lower() in names:
                raise ValueError(f"duplicate name '{stop.name}'")
        except ValueError as exc:
            messages.append(("warn", f"Skipped stored record #{i}: {exc}"))
            continue
        if stop.id <= 0 or stop.id in ids:
            stop.id = max(ids | {0}) + 1
        names.add(stop.name.lower())
        ids.add(stop.id)
        stops.append(stop)
    return stops, settings, messages

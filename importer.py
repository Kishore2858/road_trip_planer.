"""Bulk CSV import with per-row validation and an error log."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import planner
from models import Stop

REQUIRED_COLUMNS = {"name", "category", "distance_km"}


@dataclass
class ImportResult:
    added: list = field(default_factory=list)
    errors: list = field(default_factory=list)   # strings like "Row 7: distance_km 'abc' is not a number"


def import_csv(csv_path, existing_stops, avg_speed=60, log_path=None) -> ImportResult:
    """Validate every row; add good rows to ``existing_stops`` and log bad ones.

    Row numbers match a spreadsheet (header = row 1). Optional columns get defaults:
    travel_time_min is estimated, stay 0, priority 3, status planned.
    Raises FileNotFoundError / ValueError for an unreadable file or bad header.
    """
    result = ImportResult()
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        header = {(h or "").strip().lower() for h in (reader.fieldnames or [])}
        missing = REQUIRED_COLUMNS - header
        if missing:
            raise ValueError(f"CSV is missing required column(s): {', '.join(sorted(missing))}")
        for row_no, raw in enumerate(reader, start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items() if k}
            if not any(row.values()):
                continue                                   # silently ignore blank lines
            try:
                if row.get("distance_km") == "":
                    raise ValueError("distance_km is missing")
                if row.get("travel_time_min", "") == "":
                    try:
                        row["travel_time_min"] = planner.estimate_travel_minutes(float(row["distance_km"]), avg_speed)
                    except ValueError:
                        pass                               # from_dict reports the bad distance
                row.setdefault("stay_time_min", "")
                for key, default in (("stay_time_min", "0"), ("priority", "3"), ("status", "planned")):
                    if row.get(key, "") == "":
                        row[key] = default
                row.pop("id", None)
                stop = Stop.from_dict(row)
                if planner.find_duplicate(existing_stops + result.added, stop.name):
                    raise ValueError(f"duplicate stop name '{stop.name}'")
                stop.id = planner.next_id(existing_stops + result.added)
                result.added.append(stop)
            except ValueError as exc:
                result.errors.append(f"Row {row_no}: {exc}")
    existing_stops.extend(result.added)
    if log_path and result.errors:
        log = Path(log_path)
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(f"--- Import of {Path(csv_path).name} at {datetime.now():%Y-%m-%d %H:%M:%S} ---\n")
            fh.write("\n".join(result.errors) + "\n")
    return result

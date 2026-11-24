"""Export reports: Markdown, plain-text audit log and CSV."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import planner
import summary
import ui

CSV_FIELDS = ["id", "name", "category", "distance_km", "travel_time_min",
              "stay_time_min", "priority", "status", "notes"]


def _safe_cell(value):
    """Neutralise spreadsheet formula injection (cells starting with = + - @)."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _stamp():
    now = datetime.now()
    return now, now.strftime("%Y%m%d_%H%M%S")


def export_markdown(stops, out_dir, start: datetime, settings=None) -> Path:
    now, tag = _stamp()
    stats = summary.build_summary(stops, settings)
    path = Path(out_dir) / f"trip_report_{tag}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Road Trip Stop Planner - Trip Report", "",
             f"_Generated {now:%Y-%m-%d %H:%M:%S}_", "", "## Summary", "", "```"]
    lines += summary.summary_lines(stats)
    lines += ["```", "", "## Warnings", ""]
    warns = summary.collect_warnings(stops)
    lines += [f"- {w}" for w in warns] or ["- None"]
    lines += ["", "## Day-by-day plan", ""]
    for d in planner.day_plan(stops, start):
        lines.append(f"- **Day {d['day']}**: {len(d['items'])} stops, {d['km']:.0f} km, "
                     f"driving {ui.fmt_minutes(d['drive_min'])} - "
                     + ", ".join(s.name for s, _, _ in d["items"]))
    if not planner.active_stops(stops):
        lines.append("- No active stops")
    lines += ["", "## Itinerary", "",
              "| # | Stop | Category | Km | Drive | Stay | Pri | Status | Arrive | Notes |",
              "|---|------|----------|---:|------:|-----:|----:|--------|--------|-------|"]
    etas = {s.id: a for s, a, _ in planner.compute_etas(stops, start)}
    for i, s in enumerate(stops, 1):
        eta = etas.get(s.id)
        when = "-" if eta is None else f"D{(eta.date() - start.date()).days + 1} {eta:%H:%M}"
        lines.append(f"| {i} | {s.name} | {s.category} | {s.distance_km:.1f} | {ui.fmt_minutes(s.travel_time_min)} "
                     f"| {ui.fmt_minutes(s.stay_time_min)} | {s.priority} | {s.status} | {when} | {s.notes.replace('|', '/')} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def export_text(stops, out_dir, start: datetime, settings=None) -> Path:
    now, tag = _stamp()
    path = Path(out_dir) / f"trip_audit_{tag}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"[{now:%Y-%m-%d %H:%M:%S}] AUDIT LOG - Road Trip Stop Planner",
             f"[{now:%Y-%m-%d %H:%M:%S}] Records: {len(stops)}", ""]
    for i, s in enumerate(stops, 1):
        lines.append(f"[{now:%H:%M:%S}] #{i:02d} id={s.id} {s.name} | {s.category} | {s.distance_km:.1f} km | "
                     f"drive {s.travel_time_min} min | stay {s.stay_time_min} min | pri {s.priority} | "
                     f"{s.status} | notes: {s.notes or '-'}")
    lines += ["", "SUMMARY"] + summary.summary_lines(summary.build_summary(stops, settings))
    lines += ["", "WARNINGS"] + [f"  ! {w}" for w in summary.collect_warnings(stops)] 
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def export_csv(stops, out_dir) -> Path:
    _, tag = _stamp()
    path = Path(out_dir) / f"trip_stops_{tag}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for s in stops:
            writer.writerow({k: _safe_cell(v) for k, v in s.to_dict().items()})
    return path

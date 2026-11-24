# Road Trip Stop Planner

A menu-driven terminal app (Python 3.10+, **standard library only**) for arranging road-trip stops,
estimated distances and travel-time notes. Data is saved to JSON automatically and survives restarts.

## Quick start
```bash
python main.py                       # launch the app (no installs needed)
python -m unittest discover tests -v # run the 35 tests (unit, end-to-end menu flows, fuzz)
```
Tip: choose **11 - Load sample data** for an instant 41-stop Hyderabad -> Chennai -> Ooty demo trip.
Set `NO_COLOR=1` to turn off ANSI colours.

## Features (mapped to the problem brief)
| Brief requirement | Where |
|---|---|
| Interactive menu-driven terminal | `main.py`, `ui.py` |
| Defensive input validation | `validators.py` (loops until valid; Ctrl+C/Ctrl+D never crash), `models.py` (shared rules) |
| Core logic: arrange stops, distances, time notes | `planner.py` - auto time estimate, sort by priority/distance/category, move up/down, totals, ETA schedule, fuel/rest gap suggestions |
| Local persistence (JSON) | `storage.py` - auto-save after every change, atomic writes, corrupt/missing file recovery |
| Search & filter | `search.py` - keyword (name+notes), category, status, distance range, combinable |
| Executive summary | `summary.py` - totals, averages, status %, category bar chart, longest/shortest leg, busiest category |
| **Stretch:** multi-format export | `exporter.py` - Markdown, TXT audit log, CSV into `reports/` |
| **Stretch:** threshold warnings | `summary.py` - leg > 300 km, driving day > 8 h, fuel gap > 250 km, unrealistic speed, skipped top-priority stop |
| **Stretch:** bulk CSV import | `importer.py` - row-by-row errors, log in `reports/import_errors.log` |

## Menu
```
 1 Add stop              6 Search / filter         11 Load sample data
 2 View all stops        7 Trip summary            12 Day-by-day itinerary
 3 Edit stop             8 Export report           13 Update stop status
 4 Delete stop           9 Import CSV              14 Undo last change
 5 Arrange route         10 Settings                0 Exit
```

## Extra features beyond the brief
- **Undo** (option 14): reverts the last 20 changes (add, edit, delete, sort, move, import, status, sample load).
- **Day-by-day itinerary** (option 12): a hotel stop ends each day; per-day km, driving time and arrival times, with a warning if a day exceeds 8 h of driving.
- **Fuel cost estimate** in the summary and exports, from the mileage and fuel price set in Settings.
- **Quick status update** (option 13) and **sortable search results** (route, distance, priority, name).
- **Automatic backup**: every save keeps the previous version as `data/stops.json.bak`.
- **Safer CSV export**: text beginning with `= + - @` is neutralised so spreadsheets cannot run it as a formula.
- Notes can be cleared while editing by typing `-`. Quoted file paths (drag-and-drop) are accepted on import.

## Validation rules
| Field | Rule |
|---|---|
| name | 2-50 chars, must contain a letter/digit, unique (case-insensitive) |
| category | fuel, food, hotel, sightseeing, rest, other |
| distance_km | 0.1 - 5000 (distance from the previous stop) |
| travel_time_min | 1 - 10000 (Enter = auto estimate `distance / speed * 60`) |
| stay_time_min | 0 - 2880 |
| priority | whole number 1 - 5 (5 = must-do) |
| status | planned, visited, skipped |

## Design notes
- Skipped stops are excluded from totals, ETAs and warnings, but kept in the list.
- `distance_km` is the leg from the previous stop in the current order, so re-sorting is a "what-if" tool: edit distances if the real route changes.
- A hotel stop ends a driving "day" for the 8-hour daily driving warning.
- A corrupted `data/stops.json` is moved to `stops.corrupt.json` and a fresh file is created. Individual bad records are skipped with a message.

## Project layout
```
main.py  models.py  validators.py  planner.py  storage.py  search.py
summary.py  exporter.py  importer.py  ui.py
data/   sample_stops.json, sample_stops.csv, legacy_import_with_errors.csv, make_sample_data.py
reports/  exported files   |   tests/test_core.py
```

## 5-minute demo script
1. Run `python main.py`, show the welcome screen, press **11** to load sample data, then **2** to browse (pagination).
2. Press **1**, type a blank name, `abc` for distance, `99` for priority - watch each get rejected, then enter valid values.
3. **5 -> 1** sort by priority, **5 -> 5** show the ETA schedule.
4. **7** for the summary, bar chart and warnings; **6** to search (for example category `fuel`).
5. **12** day-by-day plan, **14** undo a deletion.
6. **9** import `data/legacy_import_with_errors.csv` (4 imported, 8 rejected with reasons).
7. **8** export all formats, open the Markdown file. **0** to exit, relaunch, press **2**: data is still there.

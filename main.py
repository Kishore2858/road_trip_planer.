"""Road Trip Stop Planner - menu-driven terminal application.

Run:  python main.py        (Python 3.10+, standard library only)
"""
from __future__ import annotations

import copy
import sys
from datetime import datetime
from pathlib import Path

import exporter
import importer
import planner
import search
import storage
import summary
import ui
import validators as V
from models import CATEGORIES, DIST_RANGE, PRIORITY_RANGE, STATUSES, STAY_RANGE, TRAVEL_RANGE, Stop

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "stops.json"
SAMPLE_FILE = BASE_DIR / "data" / "sample_stops.json"
REPORT_DIR = BASE_DIR / "reports"

HEADERS = ["#", "Name", "Category", "Km", "Drive", "Stay", "Pri", "Status"]
WIDTHS = [3, 30, 11, 7, 8, 8, 3, 8]
ALIGNS = ["r", "l", "l", "r", "r", "r", "r", "l"]
STATUS_COLOR = {"planned": "yellow", "visited": "green", "skipped": "red"}


class App:
    def __init__(self, data_file=DATA_FILE, report_dir=REPORT_DIR):
        self.data_file, self.report_dir = Path(data_file), Path(report_dir)
        self.stops, self.settings, messages = storage.load(self.data_file)
        self.history: list = []          # snapshots for Undo (newest last)
        for level, text in messages:
            (ui.warn if level == "warn" else ui.info)(text)

    # ---------- helpers ----------
    def save(self):
        storage.save(self.data_file, self.stops, self.settings)

    def snapshot(self):
        """Remember the current stops so the next change can be undone (keeps the last 20)."""
        self.history.append(copy.deepcopy(self.stops))
        del self.history[:-20]

    def start_datetime(self) -> datetime:
        h, m = map(int, self.settings["start_time"].split(":"))
        return datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)

    def need_stops(self) -> bool:
        if not self.stops:
            ui.info("No stops yet. Use option 1 to add one, or 11 to load sample data.")
            return False
        return True

    @staticmethod
    def rows(stops, start_index=1):
        return [[str(i), s.name, s.category, f"{s.distance_km:.1f}", ui.fmt_minutes(s.travel_time_min),
                 ui.fmt_minutes(s.stay_time_min), str(s.priority), (s.status, STATUS_COLOR[s.status])]
                for i, s in enumerate(stops, start_index)]

    def show(self, stops):
        ui.print_table(HEADERS, self.rows(stops), WIDTHS, ALIGNS)

    def pick(self, prompt="Stop number") -> int:
        return V.get_int(prompt, 1, len(self.stops)) - 1

    def prompt_stop(self, old: Stop | None = None) -> Stop:
        """Ask for every field. With ``old`` given, Enter keeps the current value."""
        while True:
            name = V.get_text("Stop name", default=old.name if old else None)
            if planner.find_duplicate(self.stops, name, ignore_id=old.id if old else None):
                ui.error(f"A stop named '{name}' already exists. Choose another name.")
                continue
            break
        category = V.get_choice("Category", CATEGORIES, default=old.category if old else "other")
        dist = V.get_float("Distance from previous stop in km", *DIST_RANGE, default=old.distance_km if old else None)
        estimate = planner.estimate_travel_minutes(dist, self.settings["avg_speed_kmh"])
        keep = old is not None and dist == old.distance_km
        travel = V.get_int("Travel time in minutes (Enter = auto estimate)", *TRAVEL_RANGE,
                           default=old.travel_time_min if keep else estimate)
        speed = dist / (travel / 60)
        if speed > summary.MAX_SPEED_KMH:
            ui.warn(f"That implies {speed:.0f} km/h - please double-check the travel time.")
        stay = V.get_int("Time spent at the stop in minutes", *STAY_RANGE, default=old.stay_time_min if old else 15)
        priority = V.get_int("Priority (5 = must-do)", *PRIORITY_RANGE, default=old.priority if old else 3)
        status = V.get_choice("Status", STATUSES, default=old.status if old else "planned")
        label = "Travel-time notes (- to clear)" if old and old.notes else "Travel-time notes"
        notes = V.get_text(label, 0, 200, default=old.notes if old else None, optional=True, require_alnum=False)
        if notes == "-":
            notes = ""
        return Stop(old.id if old else 0, name, category, dist, travel, stay, priority, status, notes)

    # ---------- menu actions ----------
    def add_stop(self):
        ui.heading("Add stop")
        new_stop = self.prompt_stop()
        self.snapshot()
        stop = planner.add_stop(self.stops, new_stop)
        self.save()
        ui.success(f"Added '{stop.name}' (id {stop.id}). Saved.")

    def view_stops(self):
        ui.heading("All stops (in route order)")
        if self.need_stops():
            self.show(self.stops)

    def edit_stop(self):
        ui.heading("Edit stop")
        if not self.need_stops():
            return
        self.show(self.stops)
        idx = self.pick("Number of the stop to edit")
        ui.info("Press Enter at any prompt to keep the current value.")
        updated = self.prompt_stop(self.stops[idx])
        self.snapshot()
        self.stops[idx] = updated
        self.save()
        ui.success("Stop updated. Saved.")

    def delete_stop(self):
        ui.heading("Delete stop")
        if not self.need_stops():
            return
        self.show(self.stops)
        idx = self.pick("Number of the stop to delete")
        if V.get_yes_no(f"Really delete '{self.stops[idx].name}'?"):
            self.snapshot()
            removed = self.stops.pop(idx)
            self.save()
            ui.success(f"Deleted '{removed.name}'. Saved.")
        else:
            ui.info("Nothing deleted.")

    def arrange(self):
        while True:
            ui.heading("Arrange route")
            if not self.need_stops():
                return
            print("1. Sort by priority (highest first)\n2. Sort by distance (shortest leg first)\n"
                  "3. Group by category\n4. Move one stop up/down\n5. Show schedule (ETAs)\n0. Back")
            choice = V.get_choice("Option", ("0", "1", "2", "3", "4", "5"))
            if choice == "0":
                return
            if choice in ("1", "2", "3"):
                mode = {"1": "priority", "2": "distance", "3": "category"}[choice]
                self.snapshot()
                self.stops = planner.sort_stops(self.stops, mode)
                self.save()
                ui.success(f"Route re-ordered by {mode}.")
                self.show(self.stops)
            elif choice == "4":
                self.show(self.stops)
                idx = self.pick("Stop to move")
                direction = V.get_choice("Direction", ("up", "down"))
                try:
                    self.snapshot()
                    new = planner.move_stop(self.stops, idx, -1 if direction == "up" else 1)
                    self.save()
                    ui.success(f"Moved to position {new + 1}.")
                except ValueError as exc:
                    self.history.pop()
                    ui.error(str(exc))
            else:
                self.schedule()

    def schedule(self):
        start = self.start_datetime()
        ui.heading(f"Schedule (leaving at {start:%H:%M})")
        etas = planner.compute_etas(self.stops, start)
        rows = [[s.name, s.category, f"D{(a.date() - start.date()).days + 1} {a:%H:%M}",
                 f"D{(d.date() - start.date()).days + 1} {d:%H:%M}"] for s, a, d in etas]
        ui.print_table(["Stop", "Category", "Arrive", "Depart"], rows, [30, 11, 9, 9])
        t = planner.trip_totals(self.stops)
        print(f"Total: {t['distance_km']:.1f} km, driving {ui.fmt_minutes(t['drive_min'])}, "
              f"stays {ui.fmt_minutes(t['stay_min'])}, whole trip {ui.fmt_minutes(t['total_min'])}")
        for stop, run in planner.distance_gaps(self.stops, 200, ("fuel", "rest")):
            ui.warn(f"Suggestion: {run:.0f} km without a fuel/rest stop by '{stop.name}' - add a break.")

    def search_stops(self):
        ui.heading("Search / filter (Enter skips a filter)")
        if not self.need_stops():
            return
        kw = V.get_text("Keyword (name or notes)", 1, 50, optional=True) or None
        cat = V.get_choice("Category", CATEGORIES, optional=True)
        status = V.get_choice("Status", STATUSES, optional=True)
        lo = V.get_float("Min distance km", 0, DIST_RANGE[1], optional=True)
        hi = V.get_float("Max distance km", 0, DIST_RANGE[1], optional=True)
        if lo is not None and hi is not None and lo > hi:
            ui.warn("Min is larger than max - swapping them.")
            lo, hi = hi, lo
        order = V.get_choice("Sort results by", ("route", "distance", "priority", "name"), default="route")
        found = search.filter_stops(self.stops, kw, cat, status, lo, hi)
        found = search.sort_results(found, order)
        ui.info(f"{len(found)} matching stop(s).")
        if found:
            ui.print_table(HEADERS, self.rows(found), WIDTHS, ALIGNS)

    def show_summary(self):
        ui.heading("Trip summary")
        stats = summary.build_summary(self.stops, self.settings)
        for line in summary.summary_lines(stats):
            print(line)
        warns = summary.collect_warnings(self.stops)
        print()
        if warns:
            for w in warns:
                ui.warn(w)
        elif self.stops:
            ui.success("No threshold warnings.")

    def export(self):
        ui.heading("Export report")
        if not self.need_stops():
            return
        fmt = V.get_choice("Format", ("markdown", "text", "csv", "all"), default="all")
        start = self.start_datetime()
        paths = []
        if fmt in ("markdown", "all"):
            paths.append(exporter.export_markdown(self.stops, self.report_dir, start, self.settings))
        if fmt in ("text", "all"):
            paths.append(exporter.export_text(self.stops, self.report_dir, start, self.settings))
        if fmt in ("csv", "all"):
            paths.append(exporter.export_csv(self.stops, self.report_dir))
        for p in paths:
            ui.success(f"Created {p}")

    def import_csv(self):
        ui.heading("Import stops from CSV")
        default = str(BASE_DIR / "data" / "legacy_import_with_errors.csv")
        raw = V.get_text("CSV file path", 1, 300, default=default)
        path = Path(raw.strip("\"'")).expanduser()      # tolerate drag-and-drop quotes
        self.snapshot()
        try:
            result = importer.import_csv(path, self.stops, self.settings["avg_speed_kmh"],
                                         self.report_dir / "import_errors.log")
        except FileNotFoundError:
            self.history.pop()
            ui.error(f"File not found: {path}")
            return
        except (ValueError, OSError, UnicodeDecodeError) as exc:
            self.history.pop()
            ui.error(f"Could not read CSV: {exc}")
            return
        if result.added:
            self.save()
        else:
            self.history.pop()
        ui.success(f"Imported {len(result.added)} row(s); rejected {len(result.errors)}.")
        for line in result.errors[:15]:
            ui.warn(line)
        if result.errors:
            ui.info(f"Full error log: {self.report_dir / 'import_errors.log'}")

    def edit_settings(self):
        ui.heading("Settings")
        self.settings["avg_speed_kmh"] = V.get_int("Average speed km/h (used for auto time estimates)", 10, 150,
                                                   default=self.settings["avg_speed_kmh"])
        self.settings["start_time"] = V.get_time("Departure time", default=self.settings["start_time"])
        self.settings["mileage_km_per_l"] = V.get_float("Vehicle mileage in km per litre", 1, 60,
                                                        default=self.settings["mileage_km_per_l"])
        self.settings["fuel_price_per_l"] = V.get_float("Fuel price per litre", 1, 1000,
                                                        default=self.settings["fuel_price_per_l"])
        self.save()
        ui.success("Settings saved.")

    def load_sample(self):
        ui.heading("Load sample data")
        if self.stops and not V.get_yes_no("This REPLACES your current stops. Continue?"):
            return
        stops, settings, messages = storage.load(SAMPLE_FILE)
        for level, text in messages:
            ui.warn(text)
        self.snapshot()
        self.stops, self.settings = stops, settings
        self.save()
        ui.success(f"Loaded {len(stops)} sample stops.")

    def day_itinerary(self):
        ui.heading("Day-by-day itinerary (a hotel stop ends each day)")
        if not self.need_stops():
            return
        start = self.start_datetime()
        days = planner.day_plan(self.stops, start)
        if not days:
            ui.info("All stops are skipped - nothing to schedule.")
        for d in days:
            print(ui.paint(f"\nDay {d['day']}", "bold") + f" - {len(d['items'])} stops, {d['km']:.0f} km, "
                  f"driving {ui.fmt_minutes(d['drive_min'])}, stays {ui.fmt_minutes(d['stay_min'])}")
            rows = [[s.name, s.category, f"D{(a.date() - start.date()).days + 1} {a:%H:%M}",
                     f"D{(dep.date() - start.date()).days + 1} {dep:%H:%M}"] for s, a, dep in d["items"]]
            ui.print_table(["Stop", "Category", "Arrive", "Depart"], rows, [30, 11, 9, 9])
            if d["drive_min"] > summary.MAX_DAILY_DRIVE_MIN:
                ui.warn(f"Day {d['day']} exceeds the {ui.fmt_minutes(summary.MAX_DAILY_DRIVE_MIN)} driving limit.")

    def update_status(self):
        ui.heading("Quick status update")
        if not self.need_stops():
            return
        self.show(self.stops)
        idx = self.pick("Number of the stop")
        stop = self.stops[idx]
        status = V.get_choice(f"New status for '{stop.name}'", STATUSES, default=stop.status)
        if status == stop.status:
            ui.info("Status unchanged.")
            return
        self.snapshot()
        stop.status = status
        self.save()
        ui.success(f"'{stop.name}' is now {status}. Saved.")

    def undo(self):
        ui.heading("Undo")
        if not self.history:
            ui.info("Nothing to undo.")
            return
        self.stops = self.history.pop()
        self.save()
        ui.success(f"Last change undone ({len(self.stops)} stops now). {len(self.history)} more undo step(s) available.")

    # ---------- main loop ----------
    def menu(self):
        return [("1", "Add stop", self.add_stop), ("2", "View all stops", self.view_stops),
                ("3", "Edit stop", self.edit_stop), ("4", "Delete stop", self.delete_stop),
                ("5", "Arrange route / schedule", self.arrange), ("6", "Search / filter", self.search_stops),
                ("7", "Trip summary", self.show_summary), ("8", "Export report", self.export),
                ("9", "Import CSV", self.import_csv), ("10", "Settings", self.edit_settings),
                ("11", "Load sample data", self.load_sample), ("12", "Day-by-day itinerary", self.day_itinerary),
                ("13", "Update stop status", self.update_status), ("14", "Undo last change", self.undo),
                ("0", "Exit", None)]

    def run(self):
        ui.banner()
        items = self.menu()
        actions = {k: fn for k, _, fn in items}
        while True:
            print()
            for key, label, _ in items:
                print(f"  {key:>2}. {label}")
            try:
                choice = V.ask("\nChoose an option: ")
            except V.UserCancelled:
                choice = "0"
            if choice == "0":
                ui.success("Data saved. Safe travels!")
                return
            action = actions.get(choice)
            if action is None:
                ui.error("Invalid option - enter a number from the menu.")
                continue
            try:
                action()
            except V.UserCancelled:
                ui.info("Cancelled - back to the menu.")
            except ValueError as exc:
                ui.error(str(exc))
            except OSError as exc:
                ui.error(f"File problem: {exc}")


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    App().run()


if __name__ == "__main__":
    main()

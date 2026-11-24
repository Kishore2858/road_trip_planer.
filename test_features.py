"""Tests for upgraded features + end-to-end menu flows. Run: python -m unittest discover tests -v"""
import builtins
import contextlib
import csv
import io
import random
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import exporter, planner, search, storage, summary   # noqa: E402,E401
import main                                          # noqa: E402
from models import Stop                              # noqa: E402


def make(name, cat="food", km=50, drive=60, stay=15, pri=3, status="planned", notes=""):
    return Stop.from_dict(dict(name=name, category=cat, distance_km=km, travel_time_min=drive,
                               stay_time_min=stay, priority=pri, status=status, notes=notes))


def run_app(inputs, data_dir, seed_sample=False):
    """Drive App.run() with scripted keyboard input; returns (app, captured stdout)."""
    (Path(data_dir) / "data").mkdir(exist_ok=True)
    if seed_sample:
        shutil.copy(ROOT / "data" / "sample_stops.json", Path(data_dir) / "data" / "stops.json")
    it = iter(inputs)

    def fake(prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise EOFError

    real, out = builtins.input, io.StringIO()
    builtins.input = fake
    try:
        with contextlib.redirect_stdout(out):
            app = main.App(Path(data_dir) / "data" / "stops.json", Path(data_dir) / "reports")
            app.run()
    finally:
        builtins.input = real
    return app, out.getvalue()


class TestNewLogic(unittest.TestCase):
    def test_fuel(self):
        litres, cost = planner.estimate_fuel(300, 15, 100)
        self.assertEqual((litres, cost), (20, 2000))
        st = summary.build_summary([make("Leg", km=300, drive=300)], dict(storage.DEFAULT_SETTINGS))
        self.assertAlmostEqual(st["fuel"]["cost"], 2000)
        self.assertIn("Estimated fuel", "\n".join(summary.summary_lines(st)))

    def test_day_plan_splits_at_hotels(self):
        stops = [make("A One", km=10, drive=60), make("B Hotel", "hotel", 10, 60, 600),
                 make("C Next", km=10, drive=60), make("D Skip", km=10, status="skipped")]
        days = planner.day_plan(stops, datetime(2026, 1, 1, 8, 0))
        self.assertEqual([len(d["items"]) for d in days], [2, 1])     # skipped stop excluded
        self.assertEqual(days[0]["drive_min"], 120)
        self.assertEqual(planner.day_plan([], datetime(2026, 1, 1)), [])

    def test_search_sort(self):
        s = [make("Bb", km=5, pri=1), make("Aa", km=9, pri=5), make("Cc", km=1, pri=3)]
        self.assertEqual([x.name for x in search.sort_results(s, "name")], ["Aa", "Bb", "Cc"])
        self.assertEqual(search.sort_results(s, "distance")[0].name, "Cc")
        self.assertEqual(search.sort_results(s, "priority")[0].name, "Aa")
        self.assertEqual(search.sort_results(s, "route"), s)

    def test_settings_sanitised(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"
            p.write_text('{"stops": [], "settings": {"avg_speed_kmh": 9999, "mileage_km_per_l": "x", '
                         '"fuel_price_per_l": 120, "start_time": "99:99"}}', encoding="utf-8")
            _, settings, _ = storage.load(p)
            self.assertEqual(settings["avg_speed_kmh"], 60)
            self.assertEqual(settings["fuel_price_per_l"], 120)
            self.assertEqual(settings["start_time"], "08:00")

    def test_backup_created(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"
            storage.save(p, [make("One Stop")])
            storage.save(p, [make("One Stop"), make("Two Stop")])
            old, _, _ = storage.load(Path(d) / "s.json.bak")
            self.assertEqual(len(old), 1)

    def test_csv_formula_injection_guard(self):
        with tempfile.TemporaryDirectory() as d:
            path = exporter.export_csv([make("=HYPERLINK(1)", notes="+cmd")], d)
            with open(path, encoding="utf-8") as fh:
                row = next(csv.DictReader(fh))
            self.assertTrue(row["name"].startswith("'="))
            self.assertTrue(row["notes"].startswith("'+"))

    def test_exports_include_new_sections(self):
        with tempfile.TemporaryDirectory() as d:
            stops = [make("A One"), make("B Hotel", "hotel")]
            md = exporter.export_markdown(stops, d, datetime(2026, 1, 1, 8), dict(storage.DEFAULT_SETTINGS))
            text = md.read_text(encoding="utf-8")
            self.assertIn("Day-by-day plan", text)
            self.assertIn("Estimated fuel", text)
            self.assertTrue(exporter.export_text(stops, d, datetime(2026, 1, 1, 8)).exists())


class TestMenuFlows(unittest.TestCase):
    def test_add_with_validation_then_persist(self):
        with tempfile.TemporaryDirectory() as d:
            app, out = run_app(["1", "", "Mysore Palace", "sightseeing", "abc", "-4", "150", "", "15", "9", "5",
                                "planned", "Visit early", "0"], d)
            self.assertEqual(len(app.stops), 1)
            self.assertIn("cannot be blank", out)
            self.assertIn("not allowed", out)                       # 'abc' rejected
            self.assertEqual(app.stops[0].travel_time_min, 150)     # auto-estimate 150 km @ 60
            self.assertEqual(app.stops[0].priority, 5)              # 9 rejected, 5 accepted
            app2, _ = run_app(["0"], d)                             # relaunch -> data persisted
            self.assertEqual(app2.stops[0].name, "Mysore Palace")

    def test_undo_restores_deleted_stop(self):
        with tempfile.TemporaryDirectory() as d:
            app, _ = run_app(["4", "q", "1", "y", "0"], d, seed_sample=True)
            self.assertEqual(len(app.stops), 40)
            app, out = run_app(["4", "q", "1", "y", "14", "0"], d, seed_sample=True)
            self.assertEqual(len(app.stops), 41)
            self.assertIn("undone", out)

    def test_undo_with_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            _, out = run_app(["14", "0"], d)
            self.assertIn("Nothing to undo", out)

    def test_status_update_and_noop(self):
        with tempfile.TemporaryDirectory() as d:
            app, out = run_app(["13", "q", "12", "visited", "0"], d, seed_sample=True)
            self.assertEqual(app.stops[11].status, "visited")
            self.assertEqual(app.history and len(app.history), 1)

    def test_clear_notes_on_edit(self):
        with tempfile.TemporaryDirectory() as d:
            # stop #2 has notes; press Enter for every field except notes, then "-" clears them
            app, _ = run_app(["3", "q", "2", "", "", "", "", "", "", "", "-", "0"], d, seed_sample=True)
            self.assertEqual(app.stops[1].notes, "")

    def test_day_itinerary_summary_export_import(self):
        with tempfile.TemporaryDirectory() as d:
            app, out = run_app(["12", "", "7", "8", "all", "9", "", "0"], d, seed_sample=True)
            self.assertIn("Day 1", out)
            self.assertIn("Estimated fuel", out)
            self.assertIn("Imported 4 row(s); rejected 8", out)
            self.assertEqual(len(app.stops), 45)
            self.assertEqual(len(list((Path(d) / "reports").glob("*"))), 4)   # md, txt, csv, error log

    def test_import_missing_file_is_safe(self):
        with tempfile.TemporaryDirectory() as d:
            app, out = run_app(["9", '"/no/such/file.csv"', "0"], d)
            self.assertIn("File not found", out)
            self.assertEqual(app.history, [])

    def test_ctrl_d_mid_prompt_returns_to_menu(self):
        with tempfile.TemporaryDirectory() as d:
            _, out = run_app(["1", "Half Entered"], d)               # input ends mid-form
            self.assertIn("Cancelled", out)


class TestFuzz(unittest.TestCase):
    TOKENS = ["", " ", "abc", "-1", "0", "1", "2", "3", "5", "7", "9", "11", "12", "13", "14", "99", "1e999", "nan",
              "3.5", "fuel", "food", "up", "down", "y", "n", "q", "Test Stop", "!!", "x" * 80, "08:30", "25:99",
              "all", "/nonexistent.csv", "visited", "200", "0.1", "5001", "é☃", "-"]

    def test_random_sessions_never_crash(self):
        for seed in range(150):
            rnd = random.Random(seed)
            with tempfile.TemporaryDirectory() as d:
                seq = [rnd.choice(self.TOKENS) for _ in range(rnd.randint(5, 100))]
                try:
                    run_app(seq, d, seed_sample=bool(seed % 2))
                except Exception as exc:                       # noqa: BLE001
                    self.fail(f"seed {seed} crashed with {exc!r}")


if __name__ == "__main__":
    unittest.main()

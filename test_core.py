"""Unit tests. Run from the project root:  python -m unittest discover tests -v"""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import importer, planner, search, storage, summary, validators   # noqa: E402,E401
from models import Stop                                            # noqa: E402


def make(name="Test Stop", cat="food", km=50, drive=60, stay=15, pri=3, status="planned", notes="", id=0):
    return Stop.from_dict(dict(id=id, name=name, category=cat, distance_km=km, travel_time_min=drive,
                               stay_time_min=stay, priority=pri, status=status, notes=notes))


class TestModelAndValidators(unittest.TestCase):
    def test_boundaries_accepted(self):
        make(km=0.1, drive=1, pri=1)
        make(km=5000, drive=10000, pri=5)

    def test_rejections(self):
        for bad in (dict(km=0), dict(km=5001), dict(pri=6), dict(pri=0), dict(name=" "),
                    dict(name="!!"), dict(cat="spa"), dict(status="done"), dict(drive=-1)):
            with self.assertRaises(ValueError, msg=str(bad)):
                make(**bad)

    def test_non_numeric(self):
        with self.assertRaises(ValueError):
            Stop.from_dict(dict(name="Abc", category="fuel", distance_km="abc",
                                travel_time_min=5, stay_time_min=0, priority=3))

    def test_parse_number(self):
        self.assertEqual(validators.parse_number("5", 1, 10, whole=True), 5)
        for raw in ("abc", "nan", "inf", "11", "0", "2.5"):
            with self.assertRaises(ValueError):
                validators.parse_number(raw, 1, 10, whole=True)


class TestPlanner(unittest.TestCase):
    def setUp(self):
        self.stops = []
        planner.add_stop(self.stops, make("A Fuel", "fuel", 100, 100, 10, 2))
        planner.add_stop(self.stops, make("B Food", "food", 20, 30, 30, 5))
        planner.add_stop(self.stops, make("C Hotel", "hotel", 60, 60, 600, 4))

    def test_duplicate_and_ids(self):
        with self.assertRaises(ValueError):
            planner.add_stop(self.stops, make("a fuel"))
        self.assertEqual([s.id for s in self.stops], [1, 2, 3])

    def test_estimate(self):
        self.assertEqual(planner.estimate_travel_minutes(120, 60), 120)
        self.assertEqual(planner.estimate_travel_minutes(0.1, 60), 1)

    def test_sorting(self):
        self.assertEqual(planner.sort_stops(self.stops, "priority")[0].name, "B Food")
        self.assertEqual(planner.sort_stops(self.stops, "distance")[0].name, "B Food")
        self.assertEqual(planner.sort_stops(self.stops, "category")[0].category, "fuel")

    def test_move(self):
        self.assertEqual(planner.move_stop(self.stops, 0, 1), 1)
        self.assertEqual(self.stops[1].name, "A Fuel")
        with self.assertRaises(ValueError):
            planner.move_stop(self.stops, 0, -1)

    def test_totals_exclude_skipped(self):
        self.stops[1].status = "skipped"
        t = planner.trip_totals(self.stops)
        self.assertEqual((t["stops"], t["distance_km"], t["drive_min"]), (2, 160, 160))

    def test_etas(self):
        etas = planner.compute_etas(self.stops, datetime(2026, 1, 1, 8, 0))
        self.assertEqual(etas[0][1], datetime(2026, 1, 1, 9, 40))
        self.assertEqual(etas[1][1], datetime(2026, 1, 1, 10, 20))

    def test_fuel_gap(self):
        self.assertEqual(len(planner.distance_gaps([make(km=300)], 250, ("fuel",))), 1)
        self.assertEqual(planner.distance_gaps(self.stops, 250, ("fuel",)), [])


class TestSearchSummary(unittest.TestCase):
    def setUp(self):
        self.stops = [make("Highway Dhaba", "food", 70, 65, notes="Breakfast"),
                      make("Shell Fuel", "fuel", 400, 300, status="visited"),
                      make("Fast Leg", "other", 260, 60, pri=5, status="skipped")]

    def test_search(self):
        self.assertEqual(len(search.filter_stops(self.stops, keyword="BREAKFAST")), 1)
        self.assertEqual(len(search.filter_stops(self.stops, category="fuel", min_km=100)), 1)
        self.assertEqual(search.filter_stops(self.stops, keyword="zzz"), [])

    def test_summary_and_warnings(self):
        st = summary.build_summary(self.stops)
        self.assertEqual(st["stops"], 2)
        self.assertEqual(st["status_counts"]["skipped"], 1)
        text = " ".join(summary.collect_warnings(self.stops))
        self.assertIn("Long leg", text)
        self.assertIn("Top-priority stop", text)

    def test_empty_summary(self):
        self.assertEqual(summary.summary_lines(summary.build_summary([])), ["No stops recorded yet."])


class TestStorageImport(unittest.TestCase):
    def test_roundtrip_and_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"
            stops, settings, msgs = storage.load(p)           # missing -> template created
            self.assertEqual(stops, []); self.assertTrue(p.exists())
            storage.save(p, [make(id=1)], {"avg_speed_kmh": 70, "start_time": "06:30"})
            stops, settings, _ = storage.load(p)
            self.assertEqual(stops[0].name, "Test Stop"); self.assertEqual(settings["avg_speed_kmh"], 70)

    def test_corrupt_file_recovered(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"
            p.write_text("{not json", encoding="utf-8")
            stops, _, msgs = storage.load(p)
            self.assertEqual(stops, []); self.assertEqual(msgs[0][0], "warn")
            self.assertTrue((Path(d) / "s.corrupt.json").exists())

    def test_bad_records_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"
            p.write_text('{"stops":[{"name":"Good Stop","category":"food","distance_km":5,"travel_time_min":5,'
                         '"stay_time_min":0,"priority":3},{"name":"","category":"x"},"junk"]}', encoding="utf-8")
            stops, _, msgs = storage.load(p)
            self.assertEqual(len(stops), 1); self.assertEqual(len(msgs), 2)

    def test_import_with_errors(self):
        existing = []
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "err.log"
            res = importer.import_csv(ROOT / "data" / "legacy_import_with_errors.csv", existing, 60, log)
            self.assertEqual(len(res.added), 4)
            self.assertEqual(len(res.errors), 8)
            self.assertTrue(res.errors[0].startswith("Row 4:"))
            self.assertTrue(log.exists())
            self.assertEqual(existing[-1].travel_time_min, 90)  # auto-estimated

    def test_import_bad_header(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.csv"; f.write_text("a,b\n1,2\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                importer.import_csv(f, [])


if __name__ == "__main__":
    unittest.main()

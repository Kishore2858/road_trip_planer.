"""Regenerates data/sample_stops.json and data/sample_stops.csv (41 realistic records).

Run from the project root:  python data/make_sample_data.py
Includes edge cases: 0.1 km leg, 320 km leg, missing notes, skipped must-do stop,
unrealistic speed, long fuel gap.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import storage                     # noqa: E402
from models import Stop            # noqa: E402

# name, category, km, drive_min, stay_min, priority, status, notes
RAW = [
    ("Hyderabad Start Point", "other", 0.1, 1, 0, 5, "visited", ""),
    ("Shamshabad Fuel Station", "fuel", 24, 30, 15, 4, "visited", "Fill tank, check tyre pressure"),
    ("Jadcherla Highway Dhaba", "food", 70, 65, 40, 3, "visited", "Breakfast stop, popular with truckers"),
    ("Kothakota Rest Area", "rest", 45, 40, 15, 2, "visited", ""),
    ("Kurnool Fuel Pump", "fuel", 120, 105, 15, 4, "visited", "NH44 toll ahead"),
    ("Kurnool Tungabhadra Viewpoint", "sightseeing", 15, 20, 30, 5, "skipped", "Skipped due to traffic"),
    ("Gooty Fort", "sightseeing", 85, 80, 60, 3, "visited", "Hill fort, steep climb"),
    ("Anantapur Tiffin Centre", "food", 72, 65, 30, 3, "visited", ""),
    ("Penukonda Rest Stop", "rest", 70, 60, 15, 2, "visited", "Clean restrooms"),
    ("Hindupur Fuel Point", "fuel", 45, 40, 10, 4, "visited", ""),
    ("Lepakshi Temple", "sightseeing", 15, 25, 90, 4, "visited", "Nandi statue, book a guide"),
    ("Devanahalli Coffee Plaza", "food", 60, 70, 30, 3, "planned", "Airport road traffic"),
    ("Bengaluru Hotel Stay", "hotel", 38, 75, 720, 5, "planned", "Overnight stay, pre-booked"),
    ("Bengaluru Palace", "sightseeing", 12, 35, 120, 2, "planned", ""),
    ("Bengaluru Fuel Stop", "fuel", 15, 25, 10, 3, "planned", ""),
    ("Electronic City Lunch", "food", 20, 40, 45, 3, "planned", "Meet cousin"),
    ("Hosur Rest Area", "rest", 30, 35, 15, 2, "planned", ""),
    ("Krishnagiri Fuel Station", "fuel", 50, 45, 10, 4, "planned", ""),
    ("Vaniyambadi Biryani House", "food", 85, 80, 50, 3, "planned", "Famous biryani"),
    ("Vellore Fort", "sightseeing", 70, 75, 75, 3, "planned", "Closed on Mondays"),
    ("Vellore Rest Plaza", "rest", 10, 20, 15, 1, "skipped", ""),
    ("Sriperumbudur Fuel Pump", "fuel", 95, 90, 10, 4, "planned", ""),
    ("Chennai Marina Beach", "sightseeing", 42, 70, 90, 5, "planned", "Sunset visit"),
    ("Chennai Hotel Stay", "hotel", 8, 25, 600, 5, "planned", "Check-in after 2 PM"),
    ("Mahabalipuram Shore Temple", "sightseeing", 58, 70, 120, 4, "planned", "UNESCO site, carry cash"),
    ("ECR Seafood Shack", "food", 35, 40, 45, 3, "planned", ""),
    ("Pondicherry Promenade", "sightseeing", 65, 75, 90, 3, "planned", ""),
    ("Pondicherry Fuel Stop", "fuel", 5, 10, 10, 3, "planned", ""),
    ("Chidambaram Nataraja Temple", "sightseeing", 70, 80, 60, 3, "planned", "Dress code applies"),
    ("Thanjavur Big Temple", "sightseeing", 120, 140, 90, 5, "planned", ""),
    ("Thanjavur Hotel Stay", "hotel", 4, 10, 600, 4, "planned", ""),
    ("Trichy Rock Fort", "sightseeing", 58, 70, 90, 3, "planned", ""),
    ("Trichy Fuel Pump", "fuel", 12, 20, 10, 3, "planned", ""),
    ("Madurai Meenakshi Temple", "sightseeing", 155, 170, 120, 5, "planned", "Long drive, start early"),
    ("Madurai Jigarthanda Break", "food", 3, 10, 20, 1, "planned", ""),
    ("Kodaikanal Hill Detour", "sightseeing", 120, 200, 180, 2, "planned", "Ghat road, avoid night driving"),
    ("Dindigul Rest Area", "rest", 95, 150, 15, 2, "planned", ""),
    ("Coimbatore Marudhamalai", "sightseeing", 320, 300, 90, 2, "planned", "Very long leg - needs a fuel stop"),
    ("Coimbatore Fuel Stop", "fuel", 8, 15, 10, 4, "planned", ""),
    ("Ooty Tea Gardens", "sightseeing", 88, 150, 120, 3, "planned", "Hairpin bends"),
    ("Highway Express Segment", "other", 260, 90, 10, 2, "planned", "Time looks too short - check estimate"),
]

KEYS = ("name", "category", "distance_km", "travel_time_min", "stay_time_min", "priority", "status", "notes")
stops = []
for i, r in enumerate(RAW, 1):
    d = dict(zip(KEYS, r))
    d["id"] = i
    stops.append(Stop.from_dict(d))

storage.save(ROOT / "data" / "sample_stops.json", stops)
with open(ROOT / "data" / "sample_stops.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(stops[0].to_dict()))
    w.writeheader()
    for s in stops:
        w.writerow(s.to_dict())
print(f"Wrote {len(stops)} records.")

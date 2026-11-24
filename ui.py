"""Terminal presentation: ANSI colours (with fallback), tables, pagination, bars."""
from __future__ import annotations

import os
import sys

USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"
if os.name == "nt" and USE_COLOR:
    os.system("")  # enables ANSI escape processing on Windows 10+ consoles

_CODES = {"red": 31, "green": 32, "yellow": 33, "cyan": 36, "bold": 1, "dim": 2}


def paint(text: str, color: str) -> str:
    return f"\033[{_CODES[color]}m{text}\033[0m" if USE_COLOR and color else str(text)


def success(msg): print(paint("[OK] ", "green") + msg)
def error(msg): print(paint("[ERROR] ", "red") + msg)
def warn(msg): print(paint("[WARN] ", "yellow") + msg)
def info(msg): print(paint("[INFO] ", "cyan") + msg)


def heading(title: str) -> None:
    print("\n" + paint(f"== {title} ==", "cyan"))


def banner() -> None:
    line = "=" * 56
    print(paint(line, "cyan"))
    print(paint("   ROAD TRIP STOP PLANNER".ljust(55) , "bold"))
    print("   Plan stops, distances and travel-time notes")
    print(paint(line, "cyan"))


def fmt_minutes(minutes: float) -> str:
    minutes = int(round(minutes))
    h, m = divmod(minutes, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def bar(value: float, maximum: float, width: int = 20) -> str:
    if maximum <= 0:
        return ""
    return "█" * max(1 if value > 0 else 0, round(value / maximum * width))


def _fit(text, width: int, align: str) -> str:
    text = str(text)
    if len(text) > width:
        text = text[: width - 1] + "…"
    return text.rjust(width) if align == "r" else text.ljust(width)


def format_row(cells, widths, aligns) -> str:
    """A cell is plain text or a (text, colour) tuple. Padding is applied before colouring."""
    out = []
    for cell, w, a in zip(cells, widths, aligns):
        text, color = cell if isinstance(cell, tuple) else (cell, None)
        out.append(paint(_fit(text, w, a), color) if color else _fit(text, w, a))
    return " | ".join(out)


def print_table(headers, rows, widths, aligns=None, page_size: int = 10) -> None:
    """Print a fixed-width table, pausing every ``page_size`` rows."""
    aligns = aligns or ["l"] * len(headers)
    head = format_row(headers, widths, ["l"] * len(headers))
    rule = "-+-".join("-" * w for w in widths)
    total = len(rows)
    for start in range(0, total, page_size):
        print(paint(head, "bold"))
        print(rule)
        for row in rows[start:start + page_size]:
            print(format_row(row, widths, aligns))
        end = min(start + page_size, total)
        print(f"Showing {start + 1}-{end} of {total}")
        if end < total:
            try:
                if input("Press Enter for next page (q to stop): ").strip().lower() == "q":
                    return
            except (EOFError, KeyboardInterrupt):
                print()
                return
            print()
    if total == 0:
        print(paint(head, "bold"))
        print(rule)
        print("(no rows)")

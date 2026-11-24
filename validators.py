"""Defensive input helpers. Every ``get_*`` function loops until the value is valid.

Ctrl+C / Ctrl+D never crash the program: they raise ``UserCancelled`` which the
menu loop catches and treats as "go back".
"""
from __future__ import annotations

import math
import re

import ui


class UserCancelled(Exception):
    """Raised when the user presses Ctrl+C / Ctrl+D (or input ends) at a prompt."""


def ask(prompt: str) -> str:
    """input() wrapper that strips whitespace and converts EOF/Ctrl+C to UserCancelled."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise UserCancelled from None


def _label(prompt: str, default=None, optional=False) -> str:
    if default is not None:
        return f"{prompt} [{default}]: "
    if optional:
        return f"{prompt} (Enter to skip): "
    return f"{prompt}: "


def parse_number(raw: str, lo, hi, whole: bool = False):
    """Convert text to a number inside [lo, hi]; raise ValueError with a friendly message."""
    try:
        value = float(raw)
    except ValueError:
        raise ValueError("Please enter a number (letters and symbols are not allowed).") from None
    if not math.isfinite(value):
        raise ValueError("That is not a valid number.")
    if whole:
        if value != int(value):
            raise ValueError("Please enter a whole number (no decimals).")
        value = int(value)
    if not lo <= value <= hi:
        raise ValueError(f"Value must be between {lo} and {hi}.")
    return value


def _get_number(prompt, lo, hi, whole, default, optional):
    while True:
        raw = ask(_label(prompt + f" ({lo}-{hi})", default, optional))
        if raw == "":
            if default is not None:
                return default
            if optional:
                return None
            ui.error("This field cannot be blank.")
            continue
        try:
            return parse_number(raw, lo, hi, whole)
        except ValueError as exc:
            ui.error(str(exc))


def get_float(prompt, lo, hi, default=None, optional=False):
    return _get_number(prompt, lo, hi, False, default, optional)


def get_int(prompt, lo, hi, default=None, optional=False):
    return _get_number(prompt, lo, hi, True, default, optional)


def get_text(prompt, min_len=2, max_len=50, default=None, optional=False, require_alnum=True):
    """Text with length limits; rejects blank (and, if require_alnum, punctuation-only) input."""
    while True:
        raw = ask(_label(prompt, default, optional))
        if raw == "":
            if default is not None:
                return default
            if optional:
                return ""
            ui.error("This field cannot be blank.")
            continue
        raw = re.sub(r"\s+", " ", raw)
        if not min_len <= len(raw) <= max_len:
            ui.error(f"Please enter {min_len}-{max_len} characters (you typed {len(raw)}).")
        elif require_alnum and not re.search(r"[A-Za-z0-9]", raw):
            ui.error("Please include at least one letter or digit.")
        else:
            return raw


def get_choice(prompt, options, default=None, optional=False):
    """Pick one of ``options`` by name, unique prefix, or list number."""
    options = tuple(options)
    shown = "/".join(options)
    while True:
        raw = ask(_label(f"{prompt} ({shown})", default, optional)).lower()
        if raw == "":
            if default is not None:
                return default
            if optional:
                return None
            ui.error("Please choose an option.")
            continue
        if raw in options:                       # exact text always wins (even "5" in a numeric menu)
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        matches = [o for o in options if o.startswith(raw)]
        if len(matches) == 1:
            return matches[0]
        ui.error(f"Invalid choice. Pick one of: {shown} (or type 1-{len(options)}).")


def get_yes_no(prompt, default=False) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        raw = ask(f"{prompt} [{hint}]: ").lower()
        if raw == "":
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        ui.error("Please answer y or n.")


def get_time(prompt, default=None) -> str:
    """24-hour HH:MM time string."""
    while True:
        raw = ask(_label(prompt + " (HH:MM)", default))
        if raw == "" and default is not None:
            return default
        m = re.fullmatch(r"(\d{1,2}):(\d{2})", raw)
        if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
            return f"{int(m.group(1)):02d}:{m.group(2)}"
        ui.error("Use 24-hour format, for example 07:30.")

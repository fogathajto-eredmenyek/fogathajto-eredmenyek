#!/usr/bin/env python3
"""Archive the live competition 48 hours after its first upload (feltoltve)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
LIVE_FILE = ROOT / "eredmenyek.json"
INDEX_FILE = ROOT / "versenyek.json"
HUNGARY = ZoneInfo("Europe/Budapest")
ARCHIVE_AFTER = timedelta(hours=48)


def parse_uploaded(value: str) -> datetime:
    value = value.strip()
    # VBA currently writes local Hungarian time without an offset.
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=HUNGARY)
        except ValueError:
            pass
    # Accept ISO timestamps carrying an explicit timezone/offset.
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=HUNGARY)
        return dt
    except ValueError as exc:
        raise ValueError(f"Nem ertelmezheto feltoltve idopont: {value!r}") from exc


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    if not LIVE_FILE.exists() or not INDEX_FILE.exists():
        print("Nincs eredmenyek.json vagy versenyek.json; nincs teendo.")
        return 0

    live_data = load_json(LIVE_FILE)
    index = load_json(INDEX_FILE)
    competitions = index.get("competitions")
    if not isinstance(competitions, list):
        raise RuntimeError("A versenyek.json competitions mezője nem lista.")

    live_entries = [c for c in competitions if c.get("live") is True]
    if not live_entries:
        print("Nincs live=true verseny a jegyzekben; nincs teendo.")
        return 0
    if len(live_entries) != 1:
        raise RuntimeError(f"Tobb live=true verseny van ({len(live_entries)}); biztonsagi okbol leall.")

    entry = live_entries[0]
    competition_id = str(entry.get("id", ""))
    live_id = str(live_data.get("versenyID", ""))
    if not competition_id or competition_id != live_id:
        raise RuntimeError(f"A jegyzek live verseny ID-ja ({competition_id}) nem egyezik a gyoker JSON ID-val ({live_id}); nem archiválok.")

    uploaded_value = live_data.get("feltoltve")
    if not uploaded_value:
        raise RuntimeError("A live eredmenyek.json-bol hianyzik a feltoltve; nem archiválok.")

    uploaded_at = parse_uploaded(str(uploaded_value))
    now = datetime.now(timezone.utc)
    age = now - uploaded_at.astimezone(timezone.utc)
    if age < ARCHIVE_AFTER:
        remaining = ARCHIVE_AFTER - age
        print(f"Meg nem telt le a 48 ora. Hatralevo ido: {remaining}.")
        return 0

    archive_path_rel = str(entry.get("data") or f"versenyek/{competition_id}/eredmenyek.json")
    # Enforce repository-relative archive path and expected competition folder.
    expected = f"versenyek/{competition_id}/eredmenyek.json"
    if archive_path_rel != expected:
        raise RuntimeError(f"Nem vart archive path a manifestben: {archive_path_rel!r}; elvart: {expected!r}.")
    archive_path = ROOT / archive_path_rel

    # Write the final snapshot first. Only after it is saved, mark the manifest archived.
    save_json(archive_path, live_data)
    entry["data"] = archive_path_rel
    entry["live"] = False
    save_json(INDEX_FILE, index)

    print(f"ARCHIVALAS SIKERES: {competition_id}; feltoltve={uploaded_value}; archív={archive_path_rel}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"HIBA: {e}", file=sys.stderr)
        raise

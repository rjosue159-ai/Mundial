#!/usr/bin/env python3
"""Descarga de stats por equipo (córners, tiros al arco) desde SofaScore.

   >>> ESTE SCRIPT SE CORRE EN TU MÁQUINA (con internet), NO en la sesión web <<<

La sesión de Claude en la web corre en un contenedor aislado sin internet, así
que este fetcher hay que ejecutarlo donde haya red: tu PC, vía el CLI o la
extensión de Claude Code (VS Code / JetBrains), o a mano:

    python scripts/fetch_stats_sofascore.py

Genera `data/team_stats.csv`, que el resto del pipeline (src/props.py,
src/parlay.py) usa automáticamente para añadir líneas de córners/tiros a la
combinada.

Notas honestas:
  - SofaScore no tiene API pública oficial; estos endpoints son los que usa su
    web. Pueden cambiar o responder 403 según la IP (usa una IP residencial /
    tu navegador). Es para uso personal; respeta su ToS y no satures el sitio.
  - Si falla, alternativa más fiable: API-Football (api-football.com), que tiene
    córners, tiros y stats de jugadores con endpoints documentados y una key
    gratis. O llena data/team_stats.csv a mano con el mismo formato que
    data/team_stats_sample.csv.
"""
from __future__ import annotations

import csv
import json
import os
import time
import urllib.parse
import urllib.request

BASE = "https://api.sofascore.com/api/v1"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept": "application/json",
}
PAUSE = 1.0  # segundos entre peticiones (sé amable con el servidor)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Los 48 equipos del Mundial 2026 (nombres como en SofaScore; ajusta si hace falta).
TEAMS = [
    "Mexico", "South Africa", "South Korea", "Czech Republic", "Canada", "Qatar",
    "Switzerland", "Bosnia and Herzegovina", "United States", "Paraguay", "Turkey",
    "Australia", "Brazil", "Morocco", "Scotland", "Haiti", "Netherlands", "Japan",
    "Sweden", "Tunisia", "Germany", "Ecuador", "Ivory Coast", "Curacao", "Belgium",
    "Egypt", "Iran", "New Zealand", "Spain", "Uruguay", "Saudi Arabia", "Cape Verde",
    "Argentina", "Austria", "Algeria", "Jordan", "France", "Senegal", "Norway",
    "Iraq", "Portugal", "Colombia", "Uzbekistan", "DR Congo", "England", "Croatia",
    "Ghana", "Panama",
]


def _get(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def find_team_id(name: str) -> int | None:
    q = urllib.parse.quote(name)
    data = _get(f"{BASE}/search/all?q={q}")
    for item in data.get("results", []):
        if item.get("type") == "team":
            return item["entity"]["id"]
    return None


def last_events(team_id: int, n: int = 10) -> list[int]:
    data = _get(f"{BASE}/team/{team_id}/events/last/0")
    evs = [e["id"] for e in data.get("events", []) if e.get("status", {}).get("type") == "finished"]
    return evs[-n:]


def event_team_stats(event_id: int, team_id: int) -> dict | None:
    """Extrae córners y tiros al arco del equipo en un partido (home/away)."""
    ev = _get(f"{BASE}/event/{event_id}")["event"]
    is_home = ev["homeTeam"]["id"] == team_id
    side = "home" if is_home else "away"
    stats = _get(f"{BASE}/event/{event_id}/statistics")
    out = {}
    for period in stats.get("statistics", []):
        if period.get("period") != "ALL":
            continue
        for group in period.get("groups", []):
            for it in group.get("statisticsItems", []):
                name = it.get("name", "").lower()
                val = it.get(side)
                try:
                    val = float(val)
                except (TypeError, ValueError):
                    continue
                if "corner" in name:
                    out["corners_for"] = val
                if name in ("shots on target", "shots on goal"):
                    out["sot_for"] = val
    return out or None


def main():
    rows = []
    for name in TEAMS:
        try:
            tid = find_team_id(name)
            time.sleep(PAUSE)
            if not tid:
                print(f"  ! no encontré id para {name}")
                continue
            cf = ca = sf = sa = []
            evs = last_events(tid, 10)
            time.sleep(PAUSE)
            cfs, sfs = [], []
            for eid in evs:
                s = event_team_stats(eid, tid)
                time.sleep(PAUSE)
                if not s:
                    continue
                if "corners_for" in s:
                    cfs.append(s["corners_for"])
                if "sot_for" in s:
                    sfs.append(s["sot_for"])
            if not cfs:
                print(f"  ! sin stats para {name}")
                continue
            avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else ""
            rows.append({
                "team": name, "matches": len(evs),
                "corners_for_avg": avg(cfs), "corners_against_avg": "",
                "sot_for_avg": avg(sfs), "sot_against_avg": "",
            })
            print(f"  ✓ {name}: córners~{avg(cfs)}  tiros~{avg(sfs)}  ({len(cfs)} partidos)")
        except Exception as e:  # noqa: BLE001
            print(f"  ! error con {name}: {e}")
            time.sleep(PAUSE)

    out = os.path.join(DATA_DIR, "team_stats.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["team", "matches", "corners_for_avg",
                                          "corners_against_avg", "sot_for_avg",
                                          "sot_against_avg"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nGuardado {out} ({len(rows)} equipos).")
    print("Completa las columnas *_against_avg si las necesitas y vuelve a correr el pipeline.")


if __name__ == "__main__":
    main()

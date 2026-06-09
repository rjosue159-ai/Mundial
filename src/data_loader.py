"""Carga y preparación de los datos de partidos.

Unifica el histórico internacional, calcula los pesos de cada partido
(temporal × importancia del torneo) y reconstruye los grupos del Mundial
2026 a partir del calendario.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from . import config


def load_international(reference_date: str | None = None,
                      since: str | None = None) -> pd.DataFrame:
    """Devuelve el histórico de partidos internacionales listo para modelar.

    Parámetros:
      - ``reference_date``: "hoy" del modelo; sólo se usan partidos anteriores.
      - ``since``: fecha de corte inferior. ``None`` usa ``config.TRAIN_SINCE``;
        pasar una fecha temprana (o ``"1900-01-01"``) carga todo el historial,
        útil para calcular Elo.

    Añade columnas:
      - ``days_ago`` / ``years_ago``: antigüedad respecto a la fecha de referencia.
      - ``w_time``: peso por decaimiento temporal exponencial.
      - ``w_tour``: peso por importancia del torneo.
      - ``weight``: producto de ambos (peso final del partido).
    """
    ref = pd.Timestamp(reference_date or config.REFERENCE_DATE)
    since_ts = pd.Timestamp(since or config.TRAIN_SINCE)
    df = pd.read_csv(config.INTL_CSV, parse_dates=["match_date"])

    # Filtro: ventana de entrenamiento, sin goles faltantes y previos a la
    # fecha de referencia (no usar el futuro para entrenar).
    df = df[df["match_date"] >= since_ts]
    df = df[df["match_date"] < ref]
    df = df.dropna(subset=["home_score", "away_score"]).copy()
    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)

    # Pesos.
    df["days_ago"] = (ref - df["match_date"]).dt.days
    df["years_ago"] = df["days_ago"] / 365.25
    decay = np.log(2) / config.HALF_LIFE_YEARS
    df["w_time"] = np.exp(-decay * df["years_ago"])
    df["w_tour"] = df["tournament"].map(config.TOURNAMENT_WEIGHTS).fillna(
        config.DEFAULT_TOURNAMENT_WEIGHT
    )
    df["weight"] = df["w_time"] * df["w_tour"]

    df = df.sort_values("match_date").reset_index(drop=True)
    return df


def load_fixtures() -> pd.DataFrame:
    """Calendario de la fase de grupos del Mundial 2026."""
    return pd.read_csv(config.FIXTURES_CSV, parse_dates=["match_date"])


def reconstruct_groups(fixtures: pd.DataFrame) -> dict[str, list[str]]:
    """Reconstruye los 12 grupos (A–L) desde el calendario.

    Dos equipos están en el mismo grupo si se enfrentan en la fase de grupos
    (round-robin de 4). Las letras se asignan por la fecha del primer partido
    de cada grupo, replicando el orden FIFA.
    """
    adj: dict[str, set[str]] = defaultdict(set)
    for _, r in fixtures.iterrows():
        adj[r.home_team].add(r.away_team)
        adj[r.away_team].add(r.home_team)

    seen: set[str] = set()
    comps: list[set[str]] = []
    for team in adj:
        if team in seen:
            continue
        stack, comp = [team], set()
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            comp.add(x)
            stack.extend(adj[x] - seen)
        comps.append(comp)

    # Orden por fecha del primer partido de cada componente.
    first_date: dict[int, pd.Timestamp] = {}
    for _, r in fixtures.iterrows():
        for ci, comp in enumerate(comps):
            if r.home_team in comp:
                if ci not in first_date or r.match_date < first_date[ci]:
                    first_date[ci] = r.match_date
                break

    order = sorted(range(len(comps)), key=lambda i: first_date[i])
    groups: dict[str, list[str]] = {}
    for pos, ci in enumerate(order):
        groups[chr(65 + pos)] = sorted(comps[ci])
    return groups


def world_cup_teams(fixtures: pd.DataFrame) -> list[str]:
    return sorted(set(fixtures.home_team) | set(fixtures.away_team))

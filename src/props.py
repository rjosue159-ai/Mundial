"""Estimación heurística de córners y tiros al arco por partido.

IMPORTANTE: esto NO es un modelo validado como el de goles. Son estimaciones
heurísticas a partir de promedios recientes por equipo (córners y tiros a favor
y en contra). Sirven para líneas de córners / over de tiros; los *props* de
jugador individual (tiros de un jugador puntual) son mucho más ruidosos y
requieren datos de alineación, así que se dejan como "comodín" manual.

Entrada esperada: un CSV de stats por equipo (lo genera el fetcher local, o se
llena a mano) con columnas:
    team, matches, corners_for_avg, corners_against_avg,
    sot_for_avg, sot_against_avg          (sot = shots on target / tiros al arco)
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
from scipy.stats import poisson

from . import config

STATS_CSV = os.path.join(config.DATA_DIR, "team_stats.csv")
STATS_SAMPLE_CSV = os.path.join(config.DATA_DIR, "team_stats_sample.csv")

# Línea de mercado: liga base ~ 0.5 para que el "over/under" tenga sentido.
LIGA_BASE = {"corners": 5.0, "sot": 4.5}


def load_team_stats(path: str | None = None) -> pd.DataFrame | None:
    """Carga el CSV de stats por equipo. Devuelve None si no existe."""
    p = path or (STATS_CSV if os.path.exists(STATS_CSV) else STATS_SAMPLE_CSV)
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p)
    df = df.set_index("team")
    return df


def _expected(home: str, away: str, stats: pd.DataFrame, kind: str):
    """Total esperado del partido para 'corners' o 'sot' (Poisson)."""
    f, a = f"{kind}_for_avg", f"{kind}_against_avg"
    base = LIGA_BASE[kind]
    if home not in stats.index or away not in stats.index:
        return 2 * base, base, base  # fallback liga
    # Esperado de cada equipo = promedio entre su producción y lo que concede el rival.
    home_exp = (stats.loc[home, f] + stats.loc[away, a]) / 2
    away_exp = (stats.loc[away, f] + stats.loc[home, a]) / 2
    return home_exp + away_exp, home_exp, away_exp


def _over_prob(line: float, total_exp: float) -> float:
    return float(1.0 - poisson.cdf(int(line), total_exp))  # P(X > line)


def props_for_fixtures(fixtures: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    """Genera selecciones de córners y tiros al arco con su cuota justa.

    Para cada partido emite varias líneas (la cercana al esperado y otras más
    altas), de modo que haya patas "long-shot" con cuota alta para la combinada.
    """
    rows = []
    for r in fixtures.itertuples(index=False):
        part = f"{r.home_team} vs {r.away_team}"
        for kind, etq in [("corners", "córners"), ("sot", "tiros al arco")]:
            tot, he, ae = _expected(r.home_team, r.away_team, stats, kind)
            base = round(tot) - 0.5
            cat = "corners" if kind == "corners" else "tiros"
            for offset in (0, 1, 2, 3, 4):       # línea base y líneas más altas
                line = max(base + offset, 1.5)
                p_over = _over_prob(line, tot)
                if 0.12 < p_over < 0.90:          # descartar líneas triviales
                    rows.append({
                        "fecha": pd.Timestamp(r.match_date).date(),
                        "partido": part,
                        "mercado": f"Más de {line:.1f} {etq} (total)",
                        "categoria": cat,
                        "esperado": round(tot, 1),
                        "prob": round(p_over, 3),
                        "cuota_justa": round(1 / p_over, 2),
                    })
    return pd.DataFrame(rows)

"""Ratings Elo de selecciones (estilo World Football Elo / FIFA).

Sirve como medida de fuerza global robusta, independiente del modelo de
goles, y como referencia para validar el Dixon-Coles.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

INITIAL = 1500.0
HOME_ADV = 65.0  # puntos Elo de ventaja por jugar en casa (no neutral)

# Factor K base por importancia del torneo.
K_BY_TOURNAMENT = {
    "FIFA World Cup": 60.0,
    "Copa América": 50.0,
    "UEFA Euro": 50.0,
    "African Cup of Nations": 50.0,
    "AFC Asian Cup": 50.0,
    "Confederations Cup": 45.0,
    "UEFA Nations League": 45.0,
    "CONCACAF Nations League": 40.0,
    "FIFA World Cup qualification": 40.0,
    "UEFA Euro qualification": 35.0,
    "African Cup of Nations qualification": 30.0,
    "AFC Asian Cup qualification": 30.0,
    "Gold Cup": 40.0,
    "CONCACAF Gold Cup": 40.0,
    "Friendly": 20.0,
}
DEFAULT_K = 30.0


def _goal_multiplier(goal_diff: int) -> float:
    """Multiplicador FIFA por margen de victoria."""
    n = abs(goal_diff)
    if n <= 1:
        return 1.0
    if n == 2:
        return 1.5
    return (11.0 + n) / 8.0


def compute_elo(matches: pd.DataFrame) -> dict[str, float]:
    """Recorre los partidos en orden y devuelve el rating Elo final por equipo.

    ``matches`` debe venir ordenado por fecha y contener home_team, away_team,
    home_score, away_score, tournament y neutral.
    """
    ratings: dict[str, float] = {}

    for r in matches.itertuples(index=False):
        rh = ratings.get(r.home_team, INITIAL)
        ra = ratings.get(r.away_team, INITIAL)

        adv = 0.0 if getattr(r, "neutral", False) else HOME_ADV
        dr = (rh + adv) - ra
        exp_home = 1.0 / (1.0 + 10.0 ** (-dr / 400.0))

        gd = int(r.home_score) - int(r.away_score)
        if gd > 0:
            score_home = 1.0
        elif gd == 0:
            score_home = 0.5
        else:
            score_home = 0.0

        k = K_BY_TOURNAMENT.get(r.tournament, DEFAULT_K) * _goal_multiplier(gd)
        delta = k * (score_home - exp_home)
        ratings[r.home_team] = rh + delta
        ratings[r.away_team] = ra - delta

    return ratings


def elo_win_probabilities(
    rating_home: float, rating_away: float, neutral: bool = True
) -> tuple[float, float]:
    """Probabilidad esperada (local, visitante) ignorando empates.

    Útil sólo como contraste; el reparto 1X2 fino lo da el Dixon-Coles.
    """
    adv = 0.0 if neutral else HOME_ADV
    dr = (rating_home + adv) - rating_away
    p_home = 1.0 / (1.0 + 10.0 ** (-dr / 400.0))
    return p_home, 1.0 - p_home

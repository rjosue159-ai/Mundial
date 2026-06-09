"""Predicción de los partidos de la fase de grupos del Mundial 2026.

Para cada partido del calendario produce: goles esperados, marcador exacto
más probable, los 3 marcadores más probables y las probabilidades 1X2.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .dixon_coles import DixonColesModel


def _is_neutral(row) -> bool:
    """¿El partido es en campo neutral para el local?

    El calendario ya trae la columna ``neutral`` (los anfitriones México,
    Canadá y EE.UU. la tienen en False cuando juegan en su país).
    """
    return bool(row.neutral)


def top_scores(mat: np.ndarray, k: int = 3) -> list[tuple[int, int, float]]:
    """Los k marcadores más probables a partir de la matriz P[x, y]."""
    flat = np.argsort(mat, axis=None)[::-1][:k]
    out = []
    for f in flat:
        i, j = np.unravel_index(f, mat.shape)
        out.append((int(i), int(j), float(mat[i, j])))
    return out


def predict_fixtures(model: DixonColesModel, fixtures: pd.DataFrame,
                     elo: dict[str, float] | None = None) -> pd.DataFrame:
    rows = []
    for r in fixtures.itertuples(index=False):
        neutral = _is_neutral(r)
        lam, mu = model.expected_goals(r.home_team, r.away_team, neutral)
        mat = model.score_matrix(r.home_team, r.away_team, neutral)
        p_home, p_draw, p_away = model.outcome_probabilities(
            r.home_team, r.away_team, neutral)
        tops = top_scores(mat, 3)
        (sh, sa, p1) = tops[0]

        # Resultado 1X2 más probable.
        result = max((("Local", p_home), ("Empate", p_draw),
                      ("Visitante", p_away)), key=lambda t: t[1])[0]

        row = {
            "fecha": pd.Timestamp(r.match_date).date(),
            "local": r.home_team,
            "visitante": r.away_team,
            "sede": r.city,
            "neutral": neutral,
            "xg_local": round(lam, 2),
            "xg_visitante": round(mu, 2),
            "marcador_exacto": f"{sh}-{sa}",
            "prob_marcador_exacto": round(p1, 3),
            "top3_marcadores": "; ".join(
                f"{a}-{b} ({p*100:.1f}%)" for a, b, p in tops),
            "prob_local": round(p_home, 3),
            "prob_empate": round(p_draw, 3),
            "prob_visitante": round(p_away, 3),
            "resultado_1x2": result,
            "prob_over_2_5": round(_prob_over(mat, 2.5), 3),
            "prob_ambos_marcan": round(_prob_btts(mat), 3),
        }
        if elo is not None:
            row["elo_local"] = round(elo.get(r.home_team, 1500), 0)
            row["elo_visitante"] = round(elo.get(r.away_team, 1500), 0)
        rows.append(row)
    return pd.DataFrame(rows)


def _prob_over(mat: np.ndarray, line: float) -> float:
    n = mat.shape[0]
    tot = 0.0
    for i in range(n):
        for j in range(n):
            if i + j > line:
                tot += mat[i, j]
    return tot


def _prob_btts(mat: np.ndarray) -> float:
    """Probabilidad de que ambos equipos marquen."""
    return float(mat[1:, 1:].sum())

"""Backtesting temporal del modelo Dixon-Coles.

Entrena con los partidos anteriores a una fecha de corte y evalúa la calidad
predictiva sobre los partidos posteriores (que el modelo no vio). Reporta
métricas estándar para pronósticos de fútbol y las compara con dos líneas
base, para dar credibilidad al modelo.

Métricas:
  - Accuracy 1X2: % de aciertos del resultado más probable.
  - Log-loss multiclase (1X2): penaliza la sobre-confianza; menor es mejor.
  - RPS (Ranked Probability Score): métrica de referencia para 1X2 porque
    respeta el orden Local > Empate > Visitante; menor es mejor.
  - Accuracy de marcador exacto.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, dixon_coles
from .data_loader import load_international


def _rps(probs: np.ndarray, outcome: int) -> float:
    """Ranked Probability Score para un partido (3 resultados ordenados)."""
    cum_p = np.cumsum(probs)
    obs = np.zeros(3)
    obs[outcome] = 1.0
    cum_o = np.cumsum(obs)
    return float(np.sum((cum_p - cum_o) ** 2) / (len(probs) - 1))


def backtest(cutoff: str = "2024-01-01",
             reference_date: str | None = None) -> dict:
    """Ajusta hasta ``cutoff`` y evalúa en [cutoff, reference_date)."""
    ref = reference_date or config.REFERENCE_DATE
    full = load_international(reference_date=ref)
    train = full[full["match_date"] < pd.Timestamp(cutoff)].copy()
    test = full[full["match_date"] >= pd.Timestamp(cutoff)].copy()

    model = dixon_coles.fit(train, verbose=False)
    # Sólo evaluamos partidos cuyos equipos vio el modelo.
    test = test[test.home_team.isin(model.teams) & test.away_team.isin(model.teams)]

    n = 0
    hits_1x2 = 0
    hits_score = 0
    sum_logloss = 0.0
    sum_rps = 0.0
    # Línea base: frecuencias globales de 1X2 en el set de entrenamiento.
    base = _base_rates(train)
    sum_logloss_base = 0.0
    sum_rps_base = 0.0

    for r in test.itertuples(index=False):
        neutral = bool(r.neutral)
        mat = model.score_matrix(r.home_team, r.away_team, neutral)
        p_home, p_draw, p_away = model.outcome_probabilities(
            r.home_team, r.away_team, neutral)
        probs = np.array([p_home, p_draw, p_away])

        gd = int(r.home_score) - int(r.away_score)
        outcome = 0 if gd > 0 else (1 if gd == 0 else 2)

        pred = int(np.argmax(probs))
        hits_1x2 += int(pred == outcome)

        pi, pj = np.unravel_index(np.argmax(mat), mat.shape)
        hits_score += int(pi == int(r.home_score) and pj == int(r.away_score))

        sum_logloss += -np.log(max(probs[outcome], 1e-12))
        sum_rps += _rps(probs, outcome)
        sum_logloss_base += -np.log(max(base[outcome], 1e-12))
        sum_rps_base += _rps(base, outcome)
        n += 1

    return {
        "cutoff": cutoff,
        "n_train": len(train),
        "n_test": n,
        "acc_1x2": hits_1x2 / n,
        "acc_marcador": hits_score / n,
        "logloss": sum_logloss / n,
        "logloss_base": sum_logloss_base / n,
        "rps": sum_rps / n,
        "rps_base": sum_rps_base / n,
    }


def _base_rates(train: pd.DataFrame) -> np.ndarray:
    gd = train.home_score - train.away_score
    w = train.weight
    p_home = w[gd > 0].sum()
    p_draw = w[gd == 0].sum()
    p_away = w[gd < 0].sum()
    tot = p_home + p_draw + p_away
    return np.array([p_home, p_draw, p_away]) / tot

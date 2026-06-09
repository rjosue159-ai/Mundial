"""Simulación Monte Carlo de la fase de grupos del Mundial 2026.

Se muestrean los 72 partidos a partir de las matrices de marcador del modelo
Dixon-Coles y se computan, sobre miles de torneos simulados, las
probabilidades de cada selección de:

  - terminar 1º, 2º, 3º o 4º de su grupo,
  - clasificar como uno de los 2 primeros,
  - clasificar como uno de los 8 mejores terceros,
  - clasificar a la fase eliminatoria (cualquiera de las dos vías).

Desempates: se aplica puntos → diferencia de goles → goles a favor → sorteo
aleatorio. (FIFA usa además el head-to-head antes del sorteo; se omite porque
afecta a una fracción pequeña de los casos y complica la vectorización. Ver
README.)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .dixon_coles import DixonColesModel


def _composite_score(pts, gd, gf, rng) -> np.ndarray:
    """Clave escalar que ordena por pts → gd → gf → aleatorio (desc.)."""
    gd_c = np.clip(gd, -90, 90)
    rand = rng.random(pts.shape)
    return pts * 1_000_000.0 + (gd_c + 100.0) * 1_000.0 + gf + rand


def simulate_groups(model: DixonColesModel, fixtures: pd.DataFrame,
                    groups: dict[str, list[str]],
                    n_sims: int = config.N_SIMULATIONS,
                    seed: int = config.RANDOM_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    N = n_sims
    n = model.max_goals + 1

    teams = sorted({t for ts in groups.values() for t in ts})
    tindex = {t: i for i, t in enumerate(teams)}
    n_teams = len(teams)
    team2group = {t: g for g, ts in groups.items() for t in ts}

    # --- Muestreo de los 72 partidos -----------------------------------
    # Para cada partido guardamos arrays (N,) de goles local y visitante.
    sampled: dict[str, list] = {g: [] for g in groups}
    for r in fixtures.itertuples(index=False):
        g = team2group[r.home_team]
        mat = model.score_matrix(r.home_team, r.away_team, bool(r.neutral))
        p = mat.flatten()
        p = p / p.sum()
        idx = rng.choice(p.size, size=N, p=p)
        hg = (idx // n).astype(np.int16)
        ag = (idx % n).astype(np.int16)
        sampled[g].append((r.home_team, r.away_team, hg, ag))

    # Acumuladores de posición final.
    cnt_pos = np.zeros((n_teams, 4), dtype=np.int64)   # 1º,2º,3º,4º
    cnt_third_qual = np.zeros(n_teams, dtype=np.int64)  # clasifica de tercero
    sum_points = np.zeros(n_teams, dtype=np.float64)

    # Datos de los terceros de cada grupo, para rankear mejores terceros.
    thirds_id = np.zeros((config.N_GROUPS, N), dtype=np.int64)
    thirds_pts = np.zeros((config.N_GROUPS, N), dtype=np.float64)
    thirds_gd = np.zeros((config.N_GROUPS, N), dtype=np.float64)
    thirds_gf = np.zeros((config.N_GROUPS, N), dtype=np.float64)

    group_order = list(groups.keys())
    for gi, g in enumerate(group_order):
        gteams = groups[g]
        gidx = {t: k for k, t in enumerate(gteams)}
        pts = np.zeros((N, 4))
        gf = np.zeros((N, 4))
        ga = np.zeros((N, 4))

        for home, away, hg, ag in sampled[g]:
            h, a = gidx[home], gidx[away]
            home_win = hg > ag
            away_win = hg < ag
            draw = hg == ag
            pts[:, h] += 3 * home_win + draw
            pts[:, a] += 3 * away_win + draw
            gf[:, h] += hg
            ga[:, h] += ag
            gf[:, a] += ag
            ga[:, a] += hg

        gd = gf - ga
        # Puntos esperados por equipo del grupo.
        for t, k in gidx.items():
            sum_points[tindex[t]] += pts[:, k].sum()

        score = _composite_score(pts, gd, gf, rng)        # (N,4)
        order = np.argsort(-score, axis=1)                 # ranking desc.

        # order[:,0]=campeón de grupo ... order[:,3]=último
        for rank in range(4):
            local_team_k = order[:, rank]                  # (N,) índice 0..3
            global_ids = np.array([tindex[gteams[k]] for k in range(4)])
            ids = global_ids[local_team_k]
            cnt_pos[:, rank] += np.bincount(ids, minlength=n_teams)

        # Guardar al tercero de este grupo.
        third_k = order[:, 2]
        global_ids = np.array([tindex[gteams[k]] for k in range(4)])
        thirds_id[gi] = global_ids[third_k]
        rows = np.arange(N)
        thirds_pts[gi] = pts[rows, third_k]
        thirds_gd[gi] = gd[rows, third_k]
        thirds_gf[gi] = gf[rows, third_k]

    # --- Mejores terceros: top 8 entre los 12 grupos, por simulación ----
    third_score = (thirds_pts * 1_000_000.0
                   + (np.clip(thirds_gd, -90, 90) + 100.0) * 1_000.0
                   + thirds_gf
                   + rng.random((config.N_GROUPS, N)))
    order_thirds = np.argsort(-third_score, axis=0)        # (12,N)
    top8_groups = order_thirds[: config.BEST_THIRDS, :]    # (8,N)
    qualified_third_ids = np.take_along_axis(thirds_id, top8_groups, axis=0)  # (8,N)
    cnt_third_qual = np.bincount(qualified_third_ids.ravel(), minlength=n_teams)

    # --- Ensamblar tabla de salida -------------------------------------
    rows = []
    for t in teams:
        i = tindex[t]
        p1, p2, p3, p4 = cnt_pos[i] / N
        p_top2 = p1 + p2
        p_third_q = cnt_third_qual[i] / N
        rows.append({
            "grupo": team2group[t],
            "equipo": t,
            "pts_esperados": round(sum_points[i] / N, 2),
            "prob_1ro": round(p1, 3),
            "prob_2do": round(p2, 3),
            "prob_3ro": round(p3, 3),
            "prob_4to": round(p4, 3),
            "prob_top2": round(p_top2, 3),
            "prob_clasif_mejor_3ro": round(p_third_q, 3),
            "prob_clasifica": round(p_top2 + p_third_q, 3),
        })
    out = pd.DataFrame(rows)
    out = out.sort_values(["grupo", "prob_clasifica"],
                          ascending=[True, False]).reset_index(drop=True)
    return out

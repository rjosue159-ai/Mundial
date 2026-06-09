"""Modelo Dixon-Coles (Poisson bivariado) con ponderación temporal.

Estima para cada selección una fuerza de ataque y de defensa, además de una
ventaja de localía global y el parámetro de corrección ``rho`` que ajusta la
dependencia en los marcadores bajos (0-0, 1-0, 0-1, 1-1), tal como en
Dixon & Coles (1997).

Para un partido local *i* vs visitante *j*:

    log(lambda) = c + home_adv * H + att[i] + def[j]      (goles del local)
    log(mu)     = c + att[j] + def[i]                      (goles del visitante)

donde ``att`` es fuerza ofensiva y ``def`` es la tendencia a *conceder* goles
(más alto = peor defensa). La verosimilitud se pondera por antigüedad e
importancia del torneo, y se regulariza con un término ridge sobre att/def que
fija la identificabilidad del modelo y encoge a los equipos con pocos datos.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

from . import config


# --------------------------------------------------------------------------
# Corrección tau de Dixon-Coles para marcadores bajos
# --------------------------------------------------------------------------
def _tau(x, y, lam, mu, rho):
    """tau vectorizado para arrays de marcadores (x, y)."""
    x = np.asarray(x)
    y = np.asarray(y)
    out = np.ones(np.broadcast(x, y, lam, mu).shape, dtype=float)
    m00 = (x == 0) & (y == 0)
    m01 = (x == 0) & (y == 1)
    m10 = (x == 1) & (y == 0)
    m11 = (x == 1) & (y == 1)
    out = np.where(m00, 1.0 - lam * mu * rho, out)
    out = np.where(m01, 1.0 + lam * rho, out)
    out = np.where(m10, 1.0 + mu * rho, out)
    out = np.where(m11, 1.0 - rho, out)
    return out


@dataclass
class DixonColesModel:
    teams: list[str]
    att: np.ndarray            # fuerza de ataque por equipo
    deff: np.ndarray           # tendencia a conceder por equipo
    intercept: float           # nivel base de goles (log)
    home_adv: float            # ventaja de localía (log)
    rho: float                 # corrección Dixon-Coles
    max_goals: int = config.MAX_GOALS

    # -- utilidades de indexado ------------------------------------------
    def _idx(self, team: str) -> int:
        return self._index[team]

    def __post_init__(self):
        self._index = {t: i for i, t in enumerate(self.teams)}

    def has_team(self, team: str) -> bool:
        return team in self._index

    # -- predicción -------------------------------------------------------
    def expected_goals(self, home: str, away: str, neutral: bool = True):
        """Goles esperados (lambda_local, mu_visitante)."""
        i, j = self._idx(home), self._idx(away)
        h = 0.0 if neutral else self.home_adv
        lam = np.exp(self.intercept + h + self.att[i] + self.deff[j])
        mu = np.exp(self.intercept + self.att[j] + self.deff[i])
        return float(lam), float(mu)

    def score_matrix(self, home: str, away: str, neutral: bool = True) -> np.ndarray:
        """Matriz P[x, y] = prob. de que el local marque x y el visitante y."""
        lam, mu = self.expected_goals(home, away, neutral)
        n = self.max_goals + 1
        px = poisson.pmf(np.arange(n), lam)
        py = poisson.pmf(np.arange(n), mu)
        mat = np.outer(px, py)
        # Corrección Dixon-Coles sólo en las 4 celdas bajas.
        mat[0, 0] *= 1.0 - lam * mu * self.rho
        mat[0, 1] *= 1.0 + lam * self.rho
        mat[1, 0] *= 1.0 + mu * self.rho
        mat[1, 1] *= 1.0 - self.rho
        mat = np.clip(mat, 0.0, None)
        mat /= mat.sum()
        return mat

    def outcome_probabilities(self, home: str, away: str, neutral: bool = True):
        """Devuelve (p_local, p_empate, p_visitante)."""
        mat = self.score_matrix(home, away, neutral)
        p_home = np.tril(mat, -1).sum()   # x > y
        p_draw = np.trace(mat)            # x == y
        p_away = np.triu(mat, 1).sum()    # x < y
        return float(p_home), float(p_draw), float(p_away)


# --------------------------------------------------------------------------
# Ajuste por máxima verosimilitud (ponderada y regularizada)
# --------------------------------------------------------------------------
def fit(matches: pd.DataFrame, verbose: bool = True) -> DixonColesModel:
    """Ajusta el modelo Dixon-Coles sobre ``matches``.

    Espera columnas: home_team, away_team, home_score, away_score, neutral,
    weight. Usa gradiente analítico + L-BFGS-B.
    """
    teams = sorted(set(matches.home_team) | set(matches.away_team))
    tindex = {t: i for i, t in enumerate(teams)}
    n_teams = len(teams)

    hi = matches.home_team.map(tindex).to_numpy()
    ai = matches.away_team.map(tindex).to_numpy()
    x = matches.home_score.to_numpy(dtype=float)
    y = matches.away_score.to_numpy(dtype=float)
    w = matches.weight.to_numpy(dtype=float)
    H = np.where(matches.neutral.to_numpy(dtype=bool), 0.0, 1.0)

    # Máscaras de las 4 celdas con corrección Dixon-Coles.
    m00 = (x == 0) & (y == 0)
    m01 = (x == 0) & (y == 1)
    m10 = (x == 1) & (y == 0)
    m11 = (x == 1) & (y == 1)

    ridge = config.RIDGE * w.sum() / n_teams  # escala con el volumen de datos

    # Vector de parámetros: [intercept, home_adv, rho, att(n), def(n)]
    def unpack(p):
        c = p[0]
        ha = p[1]
        rho = p[2]
        att = p[3 : 3 + n_teams]
        deff = p[3 + n_teams : 3 + 2 * n_teams]
        return c, ha, rho, att, deff

    def neg_loglik(p):
        c, ha, rho, att, deff = unpack(p)
        log_lam = c + ha * H + att[hi] + deff[ai]
        log_mu = c + att[ai] + deff[hi]
        lam = np.exp(log_lam)
        mu = np.exp(log_mu)

        # log-Poisson (omitimos log(x!), constante respecto a los parámetros).
        ll = x * log_lam - lam + y * log_mu - mu

        # Corrección tau.
        tau = np.ones_like(lam)
        tau = np.where(m00, 1.0 - lam * mu * rho, tau)
        tau = np.where(m01, 1.0 + lam * rho, tau)
        tau = np.where(m10, 1.0 + mu * rho, tau)
        tau = np.where(m11, 1.0 - rho, tau)
        tau = np.clip(tau, 1e-12, None)
        ll = ll + np.log(tau)

        nll = -np.sum(w * ll) + ridge * (np.sum(att ** 2) + np.sum(deff ** 2))
        return nll

    def grad(p):
        c, ha, rho, att, deff = unpack(p)
        log_lam = c + ha * H + att[hi] + deff[ai]
        log_mu = c + att[ai] + deff[hi]
        lam = np.exp(log_lam)
        mu = np.exp(log_mu)

        tau = np.ones_like(lam)
        dtau_dlam = np.zeros_like(lam)
        dtau_dmu = np.zeros_like(lam)
        dtau_drho = np.zeros_like(lam)

        tau = np.where(m00, 1.0 - lam * mu * rho, tau)
        dtau_dlam = np.where(m00, -mu * rho, dtau_dlam)
        dtau_dmu = np.where(m00, -lam * rho, dtau_dmu)
        dtau_drho = np.where(m00, -lam * mu, dtau_drho)

        tau = np.where(m01, 1.0 + lam * rho, tau)
        dtau_dlam = np.where(m01, rho, dtau_dlam)
        dtau_drho = np.where(m01, lam, dtau_drho)

        tau = np.where(m10, 1.0 + mu * rho, tau)
        dtau_dmu = np.where(m10, rho, dtau_dmu)
        dtau_drho = np.where(m10, mu, dtau_drho)

        tau = np.where(m11, 1.0 - rho, tau)
        dtau_drho = np.where(m11, -1.0, dtau_drho)
        tau = np.clip(tau, 1e-12, None)

        # dLL/dlambda y dLL/dmu (por partido).
        dll_dlam = x / lam - 1.0 + dtau_dlam / tau
        dll_dmu = y / mu - 1.0 + dtau_dmu / tau
        # cadena: dlambda/d(param en log) = lambda
        g_lam = w * dll_dlam * lam
        g_mu = w * dll_dmu * mu

        # Acumular en los gradientes (signo negativo: minimizamos -LL).
        g = np.zeros_like(p)
        g[0] = -np.sum(g_lam + g_mu)             # intercept
        g[1] = -np.sum(g_lam * H)                # home_adv
        g[2] = -np.sum(w * dtau_drho / tau)      # rho

        gatt = np.zeros(n_teams)
        gdef = np.zeros(n_teams)
        # lambda local: att[home] y def[away]
        np.add.at(gatt, hi, g_lam)
        np.add.at(gdef, ai, g_lam)
        # mu visitante: att[away] y def[home]
        np.add.at(gatt, ai, g_mu)
        np.add.at(gdef, hi, g_mu)

        g[3 : 3 + n_teams] = -gatt + 2.0 * ridge * att
        g[3 + n_teams : 3 + 2 * n_teams] = -gdef + 2.0 * ridge * deff
        return g

    # Inicialización.
    p0 = np.zeros(3 + 2 * n_teams)
    p0[0] = np.log(max(np.average(x + y, weights=w) / 2.0, 0.1))  # intercept
    p0[1] = 0.25   # ventaja localía inicial
    p0[2] = -0.05  # rho inicial (típicamente pequeño y negativo)

    # rho acotado para mantener tau > 0 en regiones razonables.
    bounds = [(None, None), (None, None), (-0.2, 0.2)] + [(None, None)] * (2 * n_teams)

    res = minimize(
        neg_loglik, p0, jac=grad, method="L-BFGS-B", bounds=bounds,
        options={"maxiter": 500, "ftol": 1e-9},
    )
    if verbose:
        print(f"  [Dixon-Coles] equipos={n_teams}  partidos={len(matches)}  "
              f"convergió={res.success}  -LL={res.fun:.1f}  iters={res.nit}")

    c, ha, rho, att, deff = unpack(res.x)
    # Centrar ataque (cosmético, no cambia predicciones) para interpretar mejor.
    shift = att.mean()
    att = att - shift
    deff = deff + shift  # compensa el desplazamiento en (att_i + def_j)
    return DixonColesModel(
        teams=teams, att=att, deff=deff,
        intercept=float(c), home_adv=float(ha), rho=float(rho),
    )

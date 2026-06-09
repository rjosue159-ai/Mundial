"""Constructor de la "apuesta loca": combinada de cuota objetivo (~50x).

Toma las predicciones del modelo (mercados de goles) y, si hay stats
disponibles, suma líneas de córners/tiros (módulo props). Busca el conjunto de
patas de partidos DISTINTOS cuyo producto de cuotas justas quede lo más cerca
posible de la cuota objetivo, y reporta la probabilidad del modelo de que toda
la combinada entre.

Nota: con cuotas justas, llegar a una cuota total objetivo equivale a fijar la
probabilidad combinada (~1/objetivo). El valor real (apostar o no) sale de
comparar estas cuotas justas con las cuotas REALES de la casa: donde la casa
pague MÁS que la cuota justa, hay valor.
"""
from __future__ import annotations

import itertools
import os

import pandas as pd

from . import config, predict, props


def _goals_legs(preds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in preds.itertuples(index=False):
        part = f"{r.local} vs {r.visitante}"
        for sel, p in [
            (f"Gana {r.local}", r.prob_local),
            ("Empate", r.prob_empate),
            (f"Gana {r.visitante}", r.prob_visitante),
            ("Más de 2.5 goles", r.prob_over_2_5),
            ("Ambos marcan", r.prob_ambos_marcan),
        ]:
            rows.append({"fecha": r.fecha, "partido": part, "mercado": sel,
                         "prob": p, "cuota_justa": round(1 / p, 2),
                         "tipo": "goles"})
    return pd.DataFrame(rows)


def build_parlay(preds: pd.DataFrame, target_odds: float = 50.0,
                 stats: pd.DataFrame | None = None,
                 min_leg: float = 2.3, max_leg: float = 5.5,
                 max_legs: int = 6) -> tuple[pd.DataFrame, dict]:
    """Devuelve (patas_elegidas, resumen) para una combinada ~target_odds."""
    legs = _goals_legs(preds)
    if stats is not None:
        pr = props.props_for_fixtures(_fixtures_from_preds(preds), stats)
        if not pr.empty:
            pr = pr.rename(columns={})
            pr["tipo"] = "props"
            legs = pd.concat([legs, pr[["fecha", "partido", "mercado", "prob",
                                        "cuota_justa", "tipo"]]],
                             ignore_index=True)

    # Pool de long-shots con VARIEDAD de cuotas (estratificado por bandas), así
    # la combinada puede aterstizar cerca del objetivo. Dentro de cada banda
    # tomamos las patas más probables (las de mejor "valor" relativo).
    band = legs[(legs.cuota_justa >= min_leg) & (legs.cuota_justa <= max_leg)]
    buckets = [(2.0, 2.6), (2.6, 3.3), (3.3, 4.2), (4.2, 5.6)]
    parts = []
    for lo, hi in buckets:
        b = band[(band.cuota_justa >= lo) & (band.cuota_justa < hi)]
        parts.append(b.sort_values("prob", ascending=False).head(7))
    pool = pd.concat(parts).drop_duplicates().reset_index(drop=True)

    # Búsqueda en numpy/python puro (rápida): combinación de partidos distintos
    # cuyo producto de cuotas quede más cerca del objetivo.
    import math
    cuotas = pool.cuota_justa.to_numpy()
    partido_code = pd.factorize(pool.partido)[0]
    n = len(pool)
    is_prop = (pool.tipo == "props").to_numpy()
    have_props = bool(is_prop.any())
    min_props = 2 if have_props else 0          # mezcla córners/tiros + goles
    min_goals = 2 if have_props else 0

    best = None  # (dist, log_odds, indices)
    log_target = math.log(target_odds)
    for k in range(max(3, min_props + min_goals), max_legs + 1):
        for combo in itertools.combinations(range(n), k):
            idx = list(combo)
            codes = partido_code[idx]
            if len(set(codes)) != k:            # patas de partidos distintos
                continue
            n_props = int(is_prop[idx].sum())
            if n_props < min_props or (k - n_props) < min_goals:
                continue                        # exigir mezcla de mercados
            log_odds = float(sum(math.log(cuotas[i]) for i in combo))
            dist = abs(log_odds - log_target)
            if best is None or dist < best[0]:
                best = (dist, log_odds, combo)
    sub = pool.iloc[list(best[2])].copy()
    odds = float(sub.cuota_justa.prod())
    sub = sub.sort_values("fecha").reset_index(drop=True)
    prob = float(sub.prob.prod())
    resumen = {
        "cuota_total_justa": round(odds, 1),
        "prob_combinada": round(prob, 4),
        "uno_de_cada": round(1 / prob),
        "n_patas": len(sub),
    }
    return sub, resumen


def _fixtures_from_preds(preds: pd.DataFrame) -> pd.DataFrame:
    return preds.rename(columns={"local": "home_team", "visitante": "away_team",
                                 "fecha": "match_date"})[
        ["match_date", "home_team", "away_team"]]


def main(target: float = 50.0):
    preds = pd.read_csv(os.path.join(config.OUT_DIR, "predicciones_partidos.csv"),
                        parse_dates=["fecha"])
    preds["fecha"] = preds["fecha"].dt.date
    stats = props.load_team_stats()
    usando_ejemplo = stats is not None and not os.path.exists(props.STATS_CSV)
    sub, resumen = build_parlay(preds, target_odds=target, stats=stats)

    print("=" * 68)
    print(f"APUESTA LOCA — combinada objetivo {target:.0f}x")
    print("=" * 68)
    fuente = "modelo de goles + stats de córners/tiros" if stats is not None \
        else "modelo de goles (sin stats de córners/tiros)"
    print(f"Fuente: {fuente}")
    print(f"Cuota total (justa del modelo): {resumen['cuota_total_justa']}x")
    print(f"Probabilidad de que entre TODA: {resumen['prob_combinada']*100:.2f}% "
          f"(~1 de cada {resumen['uno_de_cada']})\n")
    for r in sub.itertuples(index=False):
        tag = "⚽" if r.tipo == "goles" else "🚩"
        print(f"  {tag} {r.fecha}  {r.partido:<34} -> {r.mercado:<28} "
              f"| modelo {r.prob*100:4.1f}%  cuota {r.cuota_justa:.2f}")

    if usando_ejemplo:
        print("\n⚠  Las patas de córners/tiros usan data/team_stats_sample.csv "
              "(DATOS DE EJEMPLO, no reales).")
        print("   Corré scripts/fetch_stats_sofascore.py en tu PC para generar "
              "data/team_stats.csv y reemplazarlas por estimaciones reales.")
    print("\nRecordá: una combinada ~50x es un tiro largo por diseño "
          f"(~{resumen['prob_combinada']*100:.0f}% según el modelo). Apostá con cabeza.")

    out = os.path.join(config.OUT_DIR, "apuesta_loca.csv")
    sub.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\nGuardado: {out}")
    return sub, resumen


if __name__ == "__main__":
    main()

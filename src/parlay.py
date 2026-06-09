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
import math
import os

import pandas as pd

from . import config, predict, props


def _goals_legs(preds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in preds.itertuples(index=False):
        part = f"{r.local} vs {r.visitante}"
        for sel, p, cat in [
            (f"Gana {r.local}", r.prob_local, "resultado"),
            ("Empate", r.prob_empate, "resultado"),
            (f"Gana {r.visitante}", r.prob_visitante, "resultado"),
            ("Más de 2.5 goles", r.prob_over_2_5, "goles"),
            ("Ambos marcan", r.prob_ambos_marcan, "goles"),
            # Doble oportunidad ("gana o empate") — patas seguras de cuota baja.
            (f"{r.local} o empate", r.prob_local + r.prob_empate, "gana_empate"),
            (f"{r.visitante} o empate", r.prob_empate + r.prob_visitante, "gana_empate"),
        ]:
            p = min(max(p, 1e-6), 0.999)
            rows.append({"fecha": r.fecha, "partido": part, "mercado": sel,
                         "categoria": cat, "prob": p,
                         "cuota_justa": round(1 / p, 2), "tipo": "goles"})
    return pd.DataFrame(rows)


def _all_legs(preds: pd.DataFrame, stats) -> pd.DataFrame:
    """Catálogo completo de patas: goles/doble oportunidad + córners/tiros."""
    legs = _goals_legs(preds)
    if stats is not None:
        pr = props.props_for_fixtures(_fixtures_from_preds(preds), stats)
        if not pr.empty:
            pr["tipo"] = "props"
            legs = pd.concat([legs, pr[["fecha", "partido", "mercado", "categoria",
                                        "prob", "cuota_justa", "tipo"]]],
                             ignore_index=True)
    return legs


def build_mixed_parlay(preds: pd.DataFrame, stats, target_odds: float = 50.0,
                       min_por_categoria: dict | None = None,
                       max_legs: int = 7) -> tuple[pd.DataFrame, dict]:
    """Combinada que MEZCLA categorías (gana_empate + córners + tiros…).

    `min_por_categoria` exige un mínimo de patas de cada categoría; el resto las
    elige la búsqueda para acercar el producto de cuotas al objetivo.
    """
    if min_por_categoria is None:
        min_por_categoria = {"gana_empate": 2, "corners": 1, "tiros": 1}
    legs = _all_legs(preds, stats)

    # Pool por categoría con VARIEDAD de cuotas (estratificado por bandas), para
    # que la combinada pueda llegar al objetivo. Una sola pata por partido.
    bandas = {"gana_empate": (1.38, 1.75), "corners": (1.8, 4.5),
              "tiros": (1.8, 4.5), "goles": (1.9, 3.2), "resultado": (1.9, 4.5)}
    sub_bandas = [(1.38, 1.8), (1.8, 2.4), (2.4, 3.2), (3.2, 4.5)]
    parts = []
    for cat, (lo, hi) in bandas.items():
        c = legs[(legs.categoria == cat) & (legs.cuota_justa >= lo)
                 & (legs.cuota_justa <= hi)]
        c = c.sort_values("prob", ascending=False).drop_duplicates("partido")
        for slo, shi in sub_bandas:
            parts.append(c[(c.cuota_justa >= slo) & (c.cuota_justa < shi)].head(5))
    pool = pd.concat(parts).drop_duplicates(["partido", "mercado"]).reset_index(drop=True)

    import numpy as np
    cuotas = pool.cuota_justa.to_numpy()
    logc = np.log(cuotas)
    partido_code = pd.factorize(pool.partido)[0]
    log_target = math.log(target_odds)
    need = min_por_categoria
    # Índices de patas por categoría.
    by_cat = {c: pool.index[pool.categoria == c].to_numpy() for c in pool.categoria.unique()}
    base_k = sum(need.values())
    rng = np.random.default_rng(7)

    # Búsqueda aleatoria dirigida: muestrea combos válidos (mínimos por categoría
    # + partidos distintos) y guarda el de producto más cercano al objetivo.
    best = None
    for _ in range(60000):
        k = base_k + int(rng.integers(0, 5))           # base + 0..4 patas extra
        chosen, used_matches = [], set()
        ok = True
        # primero las patas mínimas exigidas por categoría
        plan = []
        for cat, m in need.items():
            plan += [cat] * m
        plan += [None] * (k - base_k)                   # extras de cualquier cat
        rng.shuffle(plan)
        for cat in plan:
            opts = by_cat.get(cat) if cat else pool.index.to_numpy()
            opts = [i for i in opts if partido_code[i] not in used_matches]
            if not opts:
                ok = False
                break
            i = int(rng.choice(opts))
            chosen.append(i)
            used_matches.add(partido_code[i])
        if not ok or len(chosen) != k:
            continue
        log_odds = float(logc[chosen].sum())
        dist = abs(log_odds - log_target)
        if best is None or dist < best[0]:
            best = (dist, list(chosen))
    if best is None:
        raise RuntimeError("No se encontró combinación; revisá stats/bandas.")
    sub = pool.loc[best[1]].sort_values(["categoria", "fecha"]).reset_index(drop=True)
    odds = float(sub.cuota_justa.prod())
    prob = float(sub.prob.prod())
    resumen = {"cuota_total_justa": round(odds, 1), "prob_combinada": round(prob, 4),
               "uno_de_cada": round(1 / prob), "n_patas": len(sub)}
    return sub, resumen


def build_safe_parlay(preds: pd.DataFrame, target_odds: float = 50.0,
                      min_leg: float = 1.40, max_leg: float = 1.60,
                      k_min: int = 6, k_max: int = 14) -> tuple[pd.DataFrame, dict]:
    """Combinada de muchas patas "seguras" (cuota baja) tipo gana-o-empate.

    Toma la mejor pata de cuota baja de cada partido (una por partido, así son
    independientes) y busca el subconjunto cuyo producto de cuotas quede más
    cerca del objetivo.
    """
    legs = _goals_legs(preds)
    cand = legs[(legs.cuota_justa >= min_leg) & (legs.cuota_justa <= max_leg)].copy()
    # Una sola pata por partido (la más probable = la más segura).
    cand = cand.sort_values("prob", ascending=False).drop_duplicates("partido")
    pool = cand.head(18).reset_index(drop=True)

    cuotas = pool.cuota_justa.to_numpy()
    n = len(pool)
    log_target = math.log(target_odds)
    best = None
    for k in range(k_min, min(k_max, n) + 1):
        for combo in itertools.combinations(range(n), k):
            log_odds = float(sum(math.log(cuotas[i]) for i in combo))
            dist = abs(log_odds - log_target)
            if best is None or dist < best[0]:
                best = (dist, combo)
    sub = pool.iloc[list(best[1])].sort_values("fecha").reset_index(drop=True)
    odds = float(sub.cuota_justa.prod())
    prob = float(sub.prob.prod())
    resumen = {"cuota_total_justa": round(odds, 1), "prob_combinada": round(prob, 4),
               "uno_de_cada": round(1 / prob), "n_patas": len(sub)}
    return sub, resumen


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


def main(target: float = 50.0, style: str = "seguras"):
    """style='seguras' (muchas patas gana-o-empate 1.40-1.60) o
    'locas' (pocas patas long-shot + córners/tiros)."""
    preds = pd.read_csv(os.path.join(config.OUT_DIR, "predicciones_partidos.csv"),
                        parse_dates=["fecha"])
    preds["fecha"] = preds["fecha"].dt.date

    usando_ejemplo = False
    if style == "mixta":
        stats = props.load_team_stats()
        usando_ejemplo = stats is not None and not os.path.exists(props.STATS_CSV)
        sub, resumen = build_mixed_parlay(preds, stats, target_odds=target)
        titulo = f"COMBINADA MIXTA (gana o empate + córners + tiros) — objetivo {target:.0f}x"
        fuente = "modelo de goles (doble oportunidad) + stats de córners/tiros"
    elif style == "seguras":
        sub, resumen = build_safe_parlay(preds, target_odds=target)
        titulo = f"COMBINADA SEGURA (gana o empate) — objetivo {target:.0f}x"
        fuente = "modelo de goles — doble oportunidad (1X / X2)"
    else:
        stats = props.load_team_stats()
        usando_ejemplo = stats is not None and not os.path.exists(props.STATS_CSV)
        sub, resumen = build_parlay(preds, target_odds=target, stats=stats)
        titulo = f"APUESTA LOCA (long-shots) — objetivo {target:.0f}x"
        fuente = "modelo de goles + stats de córners/tiros" if stats is not None \
            else "modelo de goles (sin stats de córners/tiros)"

    print("=" * 70)
    print(titulo)
    print("=" * 70)
    print(f"Fuente: {fuente}")
    print(f"Patas: {resumen['n_patas']}   |   "
          f"Cuota total (justa del modelo): {resumen['cuota_total_justa']}x")
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
    print(f"\nRecordá: una combinada ~{target:.0f}x es un tiro largo por diseño "
          f"(~{resumen['prob_combinada']*100:.1f}% según el modelo). Apostá con cabeza.")

    fname = {"seguras": "apuesta_segura.csv", "mixta": "apuesta_mixta.csv"}.get(
        style, "apuesta_loca.csv")
    out = os.path.join(config.OUT_DIR, fname)
    sub.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\nGuardado: {out}")
    return sub, resumen


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    style = "mixta"
    target = 50.0
    for a in args:
        if a in ("locas", "seguras", "mixta"):
            style = a
        else:
            try:
                target = float(a)
            except ValueError:
                pass
    main(target=target, style=style)

"""Pipeline completo del modelo predictivo del Mundial 2026.

Ejecuta de punta a punta:
  1. Carga del histórico internacional y del calendario 2026.
  2. Ratings Elo (sobre todo el historial) como medida de fuerza.
  3. Ajuste del modelo Dixon-Coles ponderado.
  4. Backtesting temporal para validar la calidad del modelo.
  5. Predicción de los 72 partidos de grupos (marcador exacto + 1X2).
  6. Simulación Monte Carlo de la fase de grupos (clasificación y posiciones).
  7. Escritura de los CSV de salida en outputs/.

Uso:
    python -m src.run_pipeline
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from . import (config, data_loader, dixon_coles, elo, export_excel, predict,
               simulate, validate)


def _print_header(txt: str):
    print("\n" + "=" * 70)
    print(txt)
    print("=" * 70)


def main():
    os.makedirs(config.OUT_DIR, exist_ok=True)
    np.random.seed(config.RANDOM_SEED)

    _print_header("1-2) Carga de datos + ratings Elo")
    fixtures = data_loader.load_fixtures()
    groups = data_loader.reconstruct_groups(fixtures)
    matches = data_loader.load_international()
    print(f"  Partidos de entrenamiento (desde {config.TRAIN_SINCE}): {len(matches)}")
    print(f"  Fecha de referencia: {config.REFERENCE_DATE}")

    # Elo sobre todo el historial disponible.
    elo_matches = data_loader.load_international(since="1900-01-01")
    elo_ratings = elo.compute_elo(elo_matches)

    _print_header("3) Ajuste del modelo Dixon-Coles")
    model = dixon_coles.fit(matches, verbose=True)
    print(f"  Intercepto (nivel base de goles, log): {model.intercept:.3f}")
    print(f"  Ventaja de localía (log): {model.home_adv:.3f} "
          f"(x{np.exp(model.home_adv):.2f} goles)")
    print(f"  rho (Dixon-Coles): {model.rho:.3f}")

    _print_header("4) Validación (backtesting temporal)")
    for cutoff in ["2023-01-01", "2024-01-01"]:
        m = validate.backtest(cutoff=cutoff)
        print(f"  Corte {cutoff}: test={m['n_test']} partidos")
        print(f"     Accuracy 1X2     : {m['acc_1x2']*100:5.1f} %")
        print(f"     Accuracy marcador: {m['acc_marcador']*100:5.1f} %")
        print(f"     Log-loss   modelo: {m['logloss']:.3f}  | base: {m['logloss_base']:.3f}")
        print(f"     RPS        modelo: {m['rps']:.3f}  | base: {m['rps_base']:.3f}")

    _print_header("5) Predicción de los 72 partidos de la fase de grupos")
    preds = predict.predict_fixtures(model, fixtures, elo_ratings)
    preds_path = os.path.join(config.OUT_DIR, "predicciones_partidos.csv")
    preds.to_csv(preds_path, index=False, encoding="utf-8-sig")
    print(f"  Guardado: {preds_path}")
    print("\n  Primeros partidos:")
    cols = ["fecha", "local", "visitante", "xg_local", "xg_visitante",
            "marcador_exacto", "prob_local", "prob_empate", "prob_visitante",
            "resultado_1x2"]
    with pd.option_context("display.width", 200, "display.max_columns", None):
        print(preds[cols].head(10).to_string(index=False))

    _print_header("6) Simulación Monte Carlo de la fase de grupos")
    print(f"  Simulaciones: {config.N_SIMULATIONS:,}")
    standings = simulate.simulate_groups(model, fixtures, groups)
    stand_path = os.path.join(config.OUT_DIR, "probabilidades_grupos.csv")
    standings.to_csv(stand_path, index=False, encoding="utf-8-sig")
    print(f"  Guardado: {stand_path}")

    # Ratings de los equipos del Mundial (Elo + att/def Dixon-Coles).
    teams = data_loader.world_cup_teams(fixtures)
    rt = []
    for t in teams:
        i = model.teams.index(t) if model.has_team(t) else None
        rt.append({
            "equipo": t,
            "grupo": next(g for g, ts in groups.items() if t in ts),
            "elo": round(elo_ratings.get(t, 1500), 0),
            "ataque_dc": round(float(model.att[i]), 3) if i is not None else None,
            "defensa_dc": round(float(model.deff[i]), 3) if i is not None else None,
        })
    ratings_df = pd.DataFrame(rt).sort_values("elo", ascending=False)
    ratings_df["rank_elo"] = range(1, len(ratings_df) + 1)
    ratings_path = os.path.join(config.OUT_DIR, "ratings_equipos.csv")
    ratings_df.to_csv(ratings_path, index=False, encoding="utf-8-sig")
    print(f"  Guardado: {ratings_path}")

    # Libro Excel listo para usar (marcadores como texto, sin bug de fechas).
    xlsx_path = os.path.join(config.OUT_DIR, "predicciones_mundial2026.xlsx")
    export_excel.write_workbook(preds, standings, ratings_df, xlsx_path)
    print(f"  Guardado: {xlsx_path}")

    _print_header("RESUMEN: probabilidad de clasificar por grupo")
    for g in sorted(groups):
        sub = standings[standings.grupo == g].sort_values(
            "prob_clasifica", ascending=False)
        print(f"\n  Grupo {g}:")
        for r in sub.itertuples(index=False):
            print(f"     {r.equipo:<24} clasifica {r.prob_clasifica*100:5.1f}%   "
                  f"(1º {r.prob_1ro*100:4.1f}%  2º {r.prob_2do*100:4.1f}%  "
                  f"3º {r.prob_3ro*100:4.1f}%)  pts~{r.pts_esperados}")

    _print_header("TOP 12 favoritos (Elo)")
    print(ratings_df.head(12)[["rank_elo", "equipo", "grupo", "elo"]]
          .to_string(index=False))

    print("\nListo. CSVs en:", config.OUT_DIR)
    return preds, standings, ratings_df


if __name__ == "__main__":
    main()

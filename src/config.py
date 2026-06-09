"""Configuración central del modelo predictivo del Mundial 2026.

Todos los parámetros ajustables del pipeline viven aquí para que el modelo
sea fácil de re-calibrar sin tocar la lógica.
"""
from __future__ import annotations

import os

# --- Rutas ---------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
OUT_DIR = os.path.join(ROOT, "outputs")

FIXTURES_CSV = os.path.join(DATA_DIR, "world_cup_2026_fixtures.csv")
INTL_CSV = os.path.join(DATA_DIR, "all_international_matches.csv")
WC_CSV = os.path.join(DATA_DIR, "world_cup_matches.csv")

# Fecha de referencia: el "hoy" del modelo. Los partidos se ponderan según
# su antigüedad respecto a esta fecha. Por defecto, el último partido del
# dataset internacional (justo antes del arranque del Mundial).
REFERENCE_DATE = "2026-06-10"

# --- Ventana de entrenamiento -------------------------------------------
# Sólo se usan partidos desde esta fecha. El decaimiento temporal se encarga
# de restar peso a los más antiguos; cortar aquí acelera el ajuste.
TRAIN_SINCE = "2010-01-01"

# Vida media (en años) del peso temporal. Un partido de hace `HALF_LIFE`
# años pesa la mitad que uno reciente.  Selecciones juegan poco -> vida media
# relativamente larga.
HALF_LIFE_YEARS = 2.5

# --- Pesos por importancia del torneo -----------------------------------
# Multiplican el peso temporal. Los amistosos informan menos que un partido
# oficial, así que pesan menos.
TOURNAMENT_WEIGHTS = {
    "FIFA World Cup": 1.00,
    "Copa América": 0.95,
    "UEFA Euro": 0.95,
    "African Cup of Nations": 0.90,
    "AFC Asian Cup": 0.90,
    "Gold Cup": 0.85,
    "CONCACAF Gold Cup": 0.85,
    "UEFA Nations League": 0.85,
    "CONCACAF Nations League": 0.80,
    "FIFA World Cup qualification": 0.90,
    "UEFA Euro qualification": 0.80,
    "African Cup of Nations qualification": 0.75,
    "AFC Asian Cup qualification": 0.75,
    "Copa América qualification": 0.80,
    "Confederations Cup": 0.85,
    "Friendly": 0.50,
}
DEFAULT_TOURNAMENT_WEIGHT = 0.65  # cualquier torneo no listado

# --- Modelo Dixon-Coles --------------------------------------------------
# Regularización L2 (ridge) sobre ataque/defensa. Resuelve la no
# identificabilidad del modelo y empuja a equipos con pocos datos hacia la
# media. Escalado por la suma de pesos en dixon_coles.py.
RIDGE = 0.01
# Goleada máxima considerada al construir la matriz de marcadores.
MAX_GOALS = 10

# --- Simulación Monte Carlo de la fase de grupos -------------------------
N_SIMULATIONS = 50_000
RANDOM_SEED = 20260611

# Formato Mundial 2026: 12 grupos de 4. Avanzan 1º y 2º de cada grupo (24)
# + los 8 mejores terceros = 32 equipos a la fase eliminatoria (dieciseisavos).
N_GROUPS = 12
QUALIFY_PER_GROUP = 2
BEST_THIRDS = 8

# Países anfitriones (juegan de local en sus sedes, no en campo neutral).
HOST_COUNTRIES = {"Mexico", "Canada", "United States"}

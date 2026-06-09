# Modelo Predictivo — Mundial 2026 (Quinielas) ⚽️

Modelo estadístico para predecir los partidos del Mundial 2026 y las
probabilidades de clasificación de cada selección. Pensado para armar la
**quiniela**: entrega el **marcador exacto** más probable de cada partido de la
fase de grupos y la **probabilidad de cada equipo de avanzar / quedar 1º, 2º,
3º o 4º** de su grupo.

> Resultado en una frase: combinamos un rating de fuerza (Elo) con un modelo de
> goles (Dixon-Coles / Poisson bivariado) entrenado sobre +15.000 partidos
> internacionales recientes, y luego simulamos la fase de grupos 50.000 veces.

---

## 1. Qué entrega

Todo se genera en `outputs/`:

| Archivo | Contenido |
|---|---|
| **`predicciones_mundial2026.xlsx`** | **Archivo listo para Excel** con 3 hojas (Partidos, Grupos, Ratings). Recomendado: los marcadores van como texto, así que Excel **no los convierte a fechas**. |
| `predicciones_partidos.csv` | Los **72 partidos** de fase de grupos: goles esperados (xG), goles local/visitante por separado, **marcador exacto** más probable, los 3 marcadores más probables, probabilidades **1X2** (local/empate/visitante), Over 2.5 y "ambos marcan". |
| `probabilidades_grupos.csv` | Por equipo: puntos esperados y **probabilidad de quedar 1º/2º/3º/4º**, de clasificar entre los 2 primeros, como mejor tercero y de **clasificar en total**. |
| `ratings_equipos.csv` | Ranking de los 48 equipos por Elo + sus parámetros de ataque/defensa del modelo Dixon-Coles. |

> ⚠️ **Si abres los `.csv` directamente en Excel**, marcadores como `1-0`, `2-0`
> o `1-1` se convierten solos a fechas (se ven como `36526`, etc.). Para evitarlo
> usa el archivo **`.xlsx`**, o en el CSV apóyate en las columnas
> `goles_local` y `goles_visitante` (enteros, nunca se corrompen).

---

## 2. Datos usados

| Archivo (`data/`) | Descripción | Uso |
|---|---|---|
| `all_international_matches.csv` | ~49.000 partidos internacionales (1872 → 2026-06-07). | **Entrenamiento** del modelo (se usan los posteriores a 2010). |
| `world_cup_2026_fixtures.csv` | Los 72 partidos de la fase de grupos del Mundial 2026. | Define qué partidos predecir y reconstruye los 12 grupos. |
| `world_cup_matches.csv` | Histórico de partidos de Mundiales. | Referencia / análisis. |
| `ResultadosMundial.xlsx` | Resultados de Mundiales recientes (2006+). | Referencia / análisis. |

Los 48 equipos del Mundial 2026 tienen historial reciente suficiente (54
partidos en promedio desde 2022), así que todos quedan bien estimados.

---

## 3. Metodología

### a) Ratings Elo (fuerza global)
Elo estilo *World Football / FIFA*: factor `K` según la importancia del torneo,
multiplicador por margen de goles y ventaja de localía. Da una medida de fuerza
robusta usada como referencia y validación.

### b) Modelo de goles: Dixon-Coles (Poisson bivariado)
Es el estándar para pronóstico de fútbol. Para un partido local *i* vs
visitante *j* estima los goles esperados:

```
log(λ)  =  c  +  ventaja_local·H  +  ataque_i  +  defensa_j     (goles del local)
log(μ)  =  c              +          ataque_j  +  defensa_i     (goles del visitante)
```

y modela los goles como Poisson, con la corrección **τ de Dixon-Coles** que
ajusta la dependencia en los marcadores bajos (0-0, 1-0, 0-1, 1-1). De ahí sale
la **matriz de probabilidad de cada marcador exacto**, y sumando sus celdas, el
**1X2**.

Detalles de la implementación (`src/dixon_coles.py`):
- **Ponderación temporal**: cada partido pesa `exp(-ln2 · años / vida_media)`,
  con vida media de **2,5 años** → lo reciente pesa más.
- **Peso por torneo**: un amistoso informa menos (0,5) que una eliminatoria
  (0,9) o un Mundial (1,0).
- **Ventaja de localía** sólo cuando el partido no es en campo neutral. En el
  Mundial sólo aplica a los anfitriones (México, Canadá, EE.UU.) en sus sedes.
- **Regularización ridge** sobre ataque/defensa: fija la identificabilidad del
  modelo y encoge hacia la media a equipos con pocos datos.
- Ajuste por **máxima verosimilitud con gradiente analítico** (L-BFGS-B);
  entrena en segundos.

### c) Simulación Monte Carlo de la fase de grupos (`src/simulate.py`)
Se muestrean los 72 partidos desde sus matrices de marcador **50.000 veces**.
En cada torneo simulado se arman las tablas, se aplican los desempates y se
determinan los clasificados (los 2 primeros de cada grupo + los **8 mejores
terceros**, formato Mundial 2026 de 48 equipos). Las probabilidades son la
frecuencia de cada evento en las 50.000 simulaciones.

---

## 4. Validación (backtesting)

Entrenando sólo con datos **anteriores** a una fecha y prediciendo los partidos
**posteriores** (que el modelo no vio):

| Corte | Partidos test | Accuracy 1X2 | Accuracy marcador | Log-loss (modelo / base) | RPS (modelo / base) |
|---|---|---|---|---|---|
| 2023-01-01 | 3.560 | **60,1 %** | 13,1 % | 0,863 / 1,054 | 0,169 / 0,229 |
| 2024-01-01 | 2.511 | **60,3 %** | 13,2 % | 0,851 / 1,054 | 0,164 / 0,227 |

- **Accuracy 1X2 ~60 %** está en el rango del estado del arte para selecciones.
- **Marcador exacto ~13 %**: acertar el marcador exacto es intrínsecamente
  difícil; este nivel es el esperado para un buen modelo.
- **Log-loss y RPS** muy por debajo de la línea base (predecir siempre las
  frecuencias promedio) → el modelo aporta señal real.

---

## 4b. Apuesta combinada "loca" (~50x) + córners/tiros

`src/parlay.py` arma una combinada de cuota objetivo (50x por defecto) eligiendo
las patas long-shot que el modelo más valora, de partidos distintos, y reporta
la **probabilidad real de que toda la combinada entre**.

```bash
python -m src.parlay        # genera outputs/apuesta_loca.csv
```

- Mercados de **goles** (gana/empate/over 2.5/ambos marcan): salen del modelo
  validado.
- Mercados de **córners y tiros al arco**: `src/props.py` los estima de forma
  **heurística** a partir de promedios por equipo (`data/team_stats.csv`). Son
  estimaciones, no un modelo validado; los *props de jugador individual* quedan
  como comodín manual (necesitan datos de alineación).

### Conseguir las stats reales de córners/tiros
Esta sesión web no tiene internet, así que las stats se bajan **desde una
máquina con red** (tu PC, vía el CLI o la extensión de Claude Code):

```bash
python scripts/fetch_stats_sofascore.py   # genera data/team_stats.csv
python -m src.parlay                       # ahora con datos reales
```

Si no existe `data/team_stats.csv`, el pipeline usa `data/team_stats_sample.csv`
(**datos de ejemplo**, solo para demostrar el flujo) y lo avisa. Alternativa más
fiable que scrapear: la API documentada de **API-Football** (tiene córners,
tiros y stats de jugadores), o llenar el CSV a mano con ese formato.

> ⚠️ Una combinada ~50x es un **tiro largo por diseño**: el modelo le da ~2 % de
> probabilidad. Es entretenimiento, no una estrategia de inversión.

## 5. Cómo correrlo

```bash
pip install -r requirements.txt
python -m src.run_pipeline
```

Genera los tres CSV en `outputs/` e imprime un resumen. Para re-calibrar
(vida media, pesos por torneo, nº de simulaciones, fecha de referencia), editar
`src/config.py`.

---

## 6. Cómo leerlo para la quiniela

- **Marcador exacto** → columna `marcador_exacto` (el más probable). Si la
  quiniela premia acercarse, mirá también `top3_marcadores`.
- **Resultado 1X2** → `resultado_1x2` y las columnas `prob_local/empate/
  visitante`. Ojo: el **empate** rara vez es el resultado *individual* más
  probable aunque ocurra ~25 % de las veces; si la quiniela es por 1X2, conviene
  mirar la probabilidad del empate, no sólo el favorito.
- **Quién pasa de grupo** → `probabilidades_grupos.csv`, columna
  `prob_clasifica` (y `prob_1ro`/`prob_2do` para las posiciones).

---

## 7. Supuestos y limitaciones

- **Desempates de grupo**: se usa puntos → diferencia de goles → goles a favor →
  sorteo. FIFA aplica además el *head-to-head* antes del sorteo; se omite porque
  afecta a pocos casos y complica la vectorización (impacto menor en las
  probabilidades agregadas).
- El modelo **no conoce** lesiones, suspensiones, convocatorias ni el estado de
  forma más allá de lo que reflejan los resultados recientes.
- La **fase eliminatoria** no se simula (el alcance pedido fue marcador exacto +
  posiciones de grupo). El código de simulación es extensible a ello.
- Las probabilidades son **estadísticas**: un favorito al 90 % igual pierde 1 de
  cada 10 veces. Es fútbol. 🙂

---

## 8. Estructura del proyecto

```
Mundial/
├── data/                     # datos de entrada
├── outputs/                  # CSV de predicciones (generados)
├── src/
│   ├── config.py             # parámetros del modelo
│   ├── data_loader.py        # carga, pesos y reconstrucción de grupos
│   ├── elo.py                # ratings Elo
│   ├── dixon_coles.py        # modelo Poisson bivariado (núcleo)
│   ├── predict.py            # predicción de los 72 partidos
│   ├── simulate.py           # Monte Carlo de la fase de grupos
│   ├── validate.py           # backtesting
│   ├── export_excel.py       # exportación a .xlsx (marcadores como texto)
│   ├── props.py              # estimación heurística de córners/tiros
│   ├── parlay.py             # constructor de la combinada "loca" (~50x)
│   └── run_pipeline.py       # orquestador (punto de entrada)
├── scripts/
│   └── fetch_stats_sofascore.py   # descarga de stats (correr en tu PC)
├── requirements.txt
└── README.md
```

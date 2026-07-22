"""
Fase 3 · Baselines: el piso que el modelo tendrá que superar.

Baselines por municipio, evaluados FUERA DE MUESTRA con partición temporal
(últimos 12 meses como prueba, el resto para entrenar; nunca aleatoria):

  - seasonal-naive: el pronóstico del mes t es el valor de t-12.
  - ETS sin tendencia: suavizamiento exponencial con estacionalidad aditiva.
  - ETS con tendencia amortiguada: igual, pero capaz de seguir una deriva.

Por qué DOS especificaciones de ETS: la primera versión de este script usaba solo
`trend=None`, lo que penaliza estructuralmente a las series con deriva (el
`monto` crece por inflación y apreciación: el ticket de Mérida pasó de ~$330 mil
en 2015 a ~$864 mil en 2026). Un baseline mal especificado infla artificialmente
al modelo que se compare contra él. Se reportan ambas para que el piso sea justo
y la diferencia quede documentada. La tendencia es AMORTIGUADA (damped) porque
extrapolar una deriva lineal a 12 meses sin freno suele explotar.

Métrica: MASE (error absoluto escalado por el error del naive dentro del train),
porque las series tienen escalas dispares (Mérida ~338/mes vs. frontera ~5/mes) y
MAE/RMSE quedarían dominados por los grandes. MASE < 1 => mejor que el naive.

ADVERTENCIA DE INTERPRETACIÓN: en series con crecimiento multiplicativo fuerte
(el `monto` en pesos corrientes), el MASE está sesgado hacia arriba — el
denominador se calcula con errores de años tempranos, cuando el nivel era mucho
más bajo. Un MASE > 1 en `monto` NO significa por sí solo que sea impronosticable;
significa que medirlo en pesos nominales con error absoluto es engañoso. De ahí
que D1 descomponga el target en acciones × ticket.

Entrada: data/interim/panel_modelado.csv
Salidas: data/processed/baselines_resumen.csv   (piso por método y target)
         data/processed/baselines_por_municipio.csv  (detalle, para la cola)
"""

from __future__ import annotations

import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

PANEL = RAIZ / "data" / "interim" / "panel_modelado.csv"
SALIDA = RAIZ / "data" / "processed" / "baselines_resumen.csv"
DETALLE = RAIZ / "data" / "processed" / "baselines_por_municipio.csv"
LLAVE = ["estado", "clave_municipio"]
H = 12          # horizonte de prueba (meses)
ESTACION = 12   # periodo estacional


def _mae(a, b):
    return float(np.mean(np.abs(np.asarray(a) - np.asarray(b))))


def _escala_naive_insample(y_train):
    """Denominador del MASE: error absoluto medio del seasonal-naive dentro del
    train. None si es 0 (serie constante) o no hay suficientes datos."""
    y = np.asarray(y_train, dtype=float)
    if len(y) <= ESTACION:
        return None
    d = float(np.mean(np.abs(y[ESTACION:] - y[:-ESTACION])))
    return d if d > 0 else None


def baseline_seasonal_naive(y_train, y_test):
    """Pronóstico = valor de hace 12 meses (cae dentro del train)."""
    hist = np.asarray(list(y_train) + list(y_test), dtype=float)
    n_train = len(y_train)
    return np.array([hist[n_train + i - ESTACION] for i in range(len(y_test))])


def baseline_ets(y_train, h, con_tendencia: bool):
    """ETS estacional aditivo. Con o sin tendencia amortiguada.
    Los avisos de convergencia se silencian aquí (son esperables en series
    cortas o ruidosas y no invalidan el ajuste)."""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    y = np.asarray(y_train, dtype=float)
    kw = dict(trend="add", damped_trend=True) if con_tendencia else dict(trend=None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ajuste = ExponentialSmoothing(
            y, seasonal="add", seasonal_periods=ESTACION,
            initialization_method="estimated", **kw).fit()
        pred = np.asarray(ajuste.forecast(h))
    return np.clip(pred, 0, None)  # conteos y montos no son negativos


METODOS = ("seasonal_naive", "ets_sin_tendencia", "ets_con_tendencia")


def evaluar_target(df: pd.DataFrame, target: str) -> pd.DataFrame:
    filas = []
    for llave, g in df.groupby(LLAVE):
        s = g.sort_values("fecha")[target].to_numpy(dtype=float)
        if len(s) < ESTACION * 2 + H:      # exige >= 2 estaciones de train
            continue
        y_train, y_test = s[:-H], s[-H:]
        escala = _escala_naive_insample(y_train)
        if escala is None:
            continue

        fila = {"estado": llave[0], "clave_municipio": llave[1], "target": target,
                "nivel_medio_test": float(np.mean(y_test))}
        fila["mase_seasonal_naive"] = _mae(y_test, baseline_seasonal_naive(y_train, y_test)) / escala
        for nombre, con_t in (("ets_sin_tendencia", False), ("ets_con_tendencia", True)):
            try:
                fila[f"mase_{nombre}"] = _mae(y_test, baseline_ets(y_train, H, con_t)) / escala
            except Exception:
                fila[f"mase_{nombre}"] = np.nan
        filas.append(fila)
    return pd.DataFrame(filas)


def diagnostico_deriva(df: pd.DataFrame) -> pd.DataFrame:
    """Cuánto creció cada target a nivel nacional entre el primer y el último año
    completo. Documenta por qué el monto es más difícil que las acciones."""
    tot = df.groupby("anio")[["acciones", "monto"]].sum()
    completos = tot.drop(index=[a for a in (2026,) if a in tot.index])
    ini, fin = completos.index.min(), completos.index.max()
    filas = []
    for col in ("acciones", "monto"):
        filas.append({"target": col, "anio_inicial": int(ini), "anio_final": int(fin),
                      "valor_inicial": float(completos.loc[ini, col]),
                      "valor_final": float(completos.loc[fin, col]),
                      "crecimiento_x": round(float(completos.loc[fin, col] / completos.loc[ini, col]), 2)})
    return pd.DataFrame(filas)


def main():
    if not PANEL.exists():
        raise SystemExit("Falta data/interim/panel_modelado.csv. Corre antes 04_panel_modelado.py.")
    df = pd.read_csv(PANEL, parse_dates=["fecha"])
    print(f"Panel: {df.groupby(LLAVE).ngroups} municipios, {df['fecha'].nunique()} meses")
    print(f"Prueba: últimos {H} meses fuera de muestra (validación temporal)\n")

    print("=" * 78)
    print("DERIVA NACIONAL — por qué el monto es más difícil que las acciones")
    print("-" * 78)
    print(diagnostico_deriva(df).to_string(index=False))

    detalles, resumen = [], []
    for target in ("acciones", "monto"):
        res = evaluar_target(df, target)
        detalles.append(res)
        for metodo in METODOS:
            v = res[f"mase_{metodo}"].dropna()
            resumen.append({
                "target": target, "metodo": metodo,
                "municipios": len(v),
                "mase_mediana": round(float(v.median()), 3),
                "mase_media": round(float(v.mean()), 3),
                "mase_p90": round(float(v.quantile(0.90)), 3),
                "pct_mase<1": round(100 * float((v < 1).mean()), 1),
            })

    tabla = pd.DataFrame(resumen)
    print("\n" + "=" * 78)
    print("PISO DE BASELINES — MASE por método y target (menor es mejor)")
    print("-" * 78)
    print(tabla.to_string(index=False))

    det = pd.concat(detalles, ignore_index=True)

    # La cola: dónde fallan los baselines. Importa para la Fase 4.
    print("\n" + "=" * 78)
    print("LA COLA — 10 municipios donde el mejor baseline falla más (acciones)")
    print("-" * 78)
    acc = det[det["target"] == "acciones"].copy()
    acc["mejor_mase"] = acc[[f"mase_{m}" for m in METODOS]].min(axis=1)
    peores = acc.nlargest(10, "mejor_mase")[
        ["estado", "clave_municipio", "nivel_medio_test", "mejor_mase"]]
    print(peores.round(2).to_string(index=False))

    mejor = tabla[tabla["target"] == "acciones"].nsmallest(1, "mase_mediana").iloc[0]
    print(f"\nPISO A BATIR (acciones): MASE mediano {mejor['mase_mediana']} "
          f"del método '{mejor['metodo']}'.")
    print("El modelo de la Fase 4 debe bajar de ahí. Si no, el entregable es el pipeline.")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(SALIDA, index=False, encoding="utf-8")
    det.to_csv(DETALLE, index=False, encoding="utf-8")
    print(f"\nGuardado: {SALIDA.name}, {DETALLE.name}")


if __name__ == "__main__":
    main()

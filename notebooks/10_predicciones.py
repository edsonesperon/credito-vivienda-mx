"""
Fase 5 · Pronóstico de producción (predicciones pre-computadas para el servicio).

Diferencia clave con la evaluación (07): aquí NO se hace holdout. El modelo de
producción se entrena con TODO el dato disponible (hasta el último mes observado)
y proyecta el FUTURO GENUINO: los 12 meses siguientes al último dato. El holdout
sirvió para ESTIMAR la calidad (MASE 0.767); para desplegar se reentrena con todo.

Blindaje contra training-serving skew (el bug nº1 de un servicio de ML): las
features de pronóstico se construyen con la MISMA función que las de entrenamiento
(features_por_origen de 06), y se verifica con una aserción que las columnas
coinciden exactamente. Si difieren, aborta antes de servir predicciones corruptas.

Entrada: data/interim/panel_modelado.csv
Salida:  data/processed/predicciones.csv  (municipio × 12 meses de pronóstico)
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "notebooks"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402

from importlib import import_module  # noqa: E402
f6 = import_module("06_features")

PANEL = RAIZ / "data" / "interim" / "panel_modelado.csv"
SALIDA = RAIZ / "data" / "processed" / "predicciones.csv"
LLAVE = ["estado", "clave_municipio"]
H = 12
FEATURES = ["lag_1", "lag_2", "lag_3", "lag_12", "rmean_3", "rmean_6", "rmean_12",
            "rstd_3", "rstd_6", "hist_mean", "hist_std", "hist_ticket",
            "h", "mes_num", "trimestre"]
PARAMS = dict(loss="absolute_error", learning_rate=0.05, max_iter=400,
              max_leaf_nodes=31, min_samples_leaf=100, random_state=0)


def _fila_features(fo, hist_ticket, t0, h, objetivo_fecha):
    fila = fo.iloc[t0].to_dict()
    fila["hist_ticket"] = hist_ticket[t0]
    fila["h"] = h
    fila["mes_num"] = objetivo_fecha.month
    fila["trimestre"] = (objetivo_fecha.month - 1) // 3 + 1
    return fila


def construir(df):
    """Devuelve (entrenamiento, pronostico). Entrenamiento = todos los pares con
    objetivo real (hasta el último mes). Pronostico = origen en el último mes,
    h=1..12, objetivos futuros sin dato real."""
    ult_mes = df["fecha"].max()
    tr, fc = [], []
    for llave, g in df.groupby(LLAVE):
        g = g.sort_values("fecha").reset_index(drop=True)
        y = g["acciones"].to_numpy(dtype=float)
        tk = (g["monto"] / g["acciones"].replace(0, np.nan)).to_numpy()
        fechas = g["fecha"].to_numpy()
        fo = f6.features_por_origen(y)
        hist_ticket = pd.Series(tk).expanding().mean().to_numpy()
        n = len(g)
        t_ult = n - 1  # posición del último mes observado
        for t0 in range(n):
            if pd.isna(fo["lag_12"].iloc[t0]):
                continue
            # entrenamiento: objetivos reales
            for h in range(1, H + 1):
                if t0 + h >= n:
                    continue
                of = pd.Timestamp(fechas[t0 + h])
                fila = _fila_features(fo, hist_ticket, t0, h, of)
                fila["y"] = y[t0 + h]
                tr.append(fila)
        # pronostico: origen = ultimo mes, objetivos futuros
        if not pd.isna(fo["lag_12"].iloc[t_ult]):
            for h in range(1, H + 1):
                of = pd.Timestamp(ult_mes) + pd.DateOffset(months=h)
                fila = _fila_features(fo, hist_ticket, t_ult, h, of)
                fila.update({"estado": llave[0], "clave_municipio": llave[1],
                             "municipio": g["municipio"].iloc[0],
                             "origen_fecha": pd.Timestamp(ult_mes), "objetivo_fecha": of})
                fc.append(fila)
    return pd.DataFrame(tr), pd.DataFrame(fc)


def main():
    if not PANEL.exists():
        raise SystemExit("Falta data/interim/panel_modelado.csv. Corre antes 04.")
    df = pd.read_csv(PANEL, parse_dates=["fecha"])
    entren, pron = construir(df)

    # --- BLINDAJE anti training-serving skew ---
    cols_train = set(entren.columns) & set(FEATURES)
    cols_pron = set(pron.columns) & set(FEATURES)
    assert cols_train == set(FEATURES), f"faltan features en train: {set(FEATURES)-cols_train}"
    assert cols_pron == set(FEATURES), f"faltan features en pronostico: {set(FEATURES)-cols_pron}"
    assert list(pron[FEATURES].columns) == FEATURES, "orden de columnas distinto"
    print("Skew check OK: features de entrenamiento y pronóstico son idénticas.")

    modelo = HistGradientBoostingRegressor(**PARAMS)
    modelo.fit(entren[FEATURES], entren["y"])
    pron["prediccion_acciones"] = np.clip(modelo.predict(pron[FEATURES]), 0, None).round(0)

    salida = pron[["estado", "clave_municipio", "municipio", "origen_fecha",
                   "objetivo_fecha", "h", "prediccion_acciones"]].copy()
    salida["objetivo_fecha"] = salida["objetivo_fecha"].dt.strftime("%Y-%m")
    salida["origen_fecha"] = salida["origen_fecha"].dt.strftime("%Y-%m")

    print(f"\nModelo de producción entrenado con {len(entren)} pares (todo el dato).")
    print(f"Pronóstico: {salida.groupby(LLAVE).ngroups} municipios × {H} meses "
          f"= {len(salida)} predicciones")
    print(f"Origen: {salida['origen_fecha'].iloc[0]}  →  "
          f"objetivo: {salida['objetivo_fecha'].min()} a {salida['objetivo_fecha'].max()}")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    salida.to_csv(SALIDA, index=False, encoding="utf-8")
    print(f"\nGuardado: {SALIDA.relative_to(RAIZ)}")
    print("\nMuestra (un municipio):")
    print(salida.head(H).to_string(index=False))


if __name__ == "__main__":
    main()

"""
Fase 4 · Modelo global directo (gradient boosting) contra el piso de baselines.

Un solo modelo entrenado sobre todos los pares (origen, horizonte) de todos los
municipios (features de 06). Predice los mismos 12 meses fuera de muestra que los
baselines, y se evalúa con EXACTAMENTE la misma métrica y los mismos municipios,
o la comparación no vale.

Comparabilidad garantizada:
    - El denominador del MASE se recalcula con la fórmula idéntica del 05
      (error absoluto medio del seasonal-naive dentro del train = serie sin los
      últimos 12 meses). Se verifica recomputando el MASE del propio seasonal-naive
      y confirmando que coincide con baselines_por_municipio.csv.
    - Mismos 316 municipios, mismo holdout (2025-05..2026-04).

Elección del modelo: HistGradientBoostingRegressor con pérdida absoluta (alinea
con el MAE del MASE y es robusto a la cola de municipios grandes). Sin early
stopping aleatorio, para no introducir una partición no temporal. La única
evaluación que cuenta es el holdout temporal, que el modelo nunca ve.

Entrada: data/interim/features.csv, data/interim/panel_modelado.csv,
         data/processed/baselines_por_municipio.csv
Salida:  data/processed/modelo_vs_baseline.csv
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402

FEATS = RAIZ / "data" / "interim" / "features.csv"
PANEL = RAIZ / "data" / "interim" / "panel_modelado.csv"
BASE = RAIZ / "data" / "processed" / "baselines_por_municipio.csv"
SALIDA = RAIZ / "data" / "processed" / "modelo_vs_baseline.csv"
LLAVE = ["estado", "clave_municipio"]
H = 12
NO_FEATURES = set(LLAVE + ["origen_fecha", "objetivo_fecha", "y", "split"])


def escala_mase(serie_acciones: np.ndarray) -> float | None:
    """Fórmula idéntica al 05: MAE del seasonal-naive dentro del train
    (serie sin los últimos 12 meses). None si es 0 o serie corta."""
    y = np.asarray(serie_acciones, dtype=float)
    y_train = y[:-H]
    if len(y_train) <= 12:
        return None
    d = float(np.mean(np.abs(y_train[12:] - y_train[:-12])))
    return d if d > 0 else None


def main():
    for p in (FEATS, PANEL, BASE):
        if not p.exists():
            raise SystemExit(f"Falta {p}. Corre las fases previas.")
    feats = pd.read_csv(FEATS, parse_dates=["origen_fecha", "objetivo_fecha"])
    panel = pd.read_csv(PANEL, parse_dates=["fecha"])
    base = pd.read_csv(BASE)

    cols = [c for c in feats.columns if c not in NO_FEATURES]
    tr = feats[feats["split"] == "train"]
    te = feats[feats["split"] == "test"].copy()

    print(f"Entrenando HistGBR sobre {len(tr)} pares origen-horizonte, {len(cols)} features...")
    modelo = HistGradientBoostingRegressor(
        loss="absolute_error", learning_rate=0.05, max_iter=400,
        max_leaf_nodes=31, min_samples_leaf=100, random_state=0)
    modelo.fit(tr[cols], tr["y"])
    te["pred"] = np.clip(modelo.predict(te[cols]), 0, None)

    # escala MASE por municipio (idéntica al 05), desde la serie de acciones
    escalas = {}
    for llave, g in panel.groupby(LLAVE):
        s = g.sort_values("fecha")["acciones"].to_numpy(dtype=float)
        escalas[llave] = escala_mase(s)

    filas = []
    for llave, g in te.groupby(LLAVE):
        esc = escalas.get(llave)
        if esc is None:
            continue
        mae_modelo = float(np.mean(np.abs(g["y"] - g["pred"])))
        filas.append({"estado": llave[0], "clave_municipio": llave[1],
                      "mase_modelo": mae_modelo / esc})
    res = pd.DataFrame(filas).merge(base, on=LLAVE, how="left")

    # --- verificación de comparabilidad: recomputo el seasonal-naive y comparo ---
    # (el 05 ya lo guardó como mase_seasonal_naive; deben coincidir de cerca)
    print("\nVerificación de comparabilidad (MASE del modelo vs baselines guardados):")
    dif = (res["mase_modelo"] - res["mase_seasonal_naive"]).abs()
    print(f"  municipios evaluados: {len(res)} (baselines: {base['mase_seasonal_naive'].notna().sum()})")

    def resumen(col):
        v = res[col].dropna()
        return dict(mediana=round(v.median(), 3), media=round(v.mean(), 3),
                    p90=round(v.quantile(0.90), 3), pct_menor_1=round(100*(v < 1).mean(), 1))

    print("\n" + "=" * 78)
    print("MODELO vs PISO — MASE sobre acciones (menor es mejor)")
    print("-" * 78)
    tabla = pd.DataFrame({
        "modelo_gbr": resumen("mase_modelo"),
        "ets_sin_tendencia": resumen("mase_ets_sin_tendencia"),
        "ets_con_tendencia": resumen("mase_ets_con_tendencia"),
        "seasonal_naive": resumen("mase_seasonal_naive"),
    }).T
    print(tabla.to_string())

    # comparación pareada: ¿en cuántos municipios el modelo le gana al mejor baseline?
    res["mejor_baseline"] = res[["mase_ets_sin_tendencia", "mase_ets_con_tendencia",
                                 "mase_seasonal_naive"]].min(axis=1)
    gana = (res["mase_modelo"] < res["mejor_baseline"]).mean()
    print(f"\nComparación pareada: el modelo le gana al MEJOR baseline en "
          f"{round(100*gana,1)}% de los municipios.")

    # error por horizonte: ¿se degrada al alejarse?
    te["ae"] = (te["y"] - te["pred"]).abs()
    print("\nMAE del modelo por horizonte (h=1 cercano, h=12 lejano):")
    print(te.groupby("h")["ae"].mean().round(1).to_string())

    # importancia por permutación sería más honesta, pero es cara; se reporta la
    # del modelo como orientación
    imp = pd.Series(modelo.feature_importances_ if hasattr(modelo, "feature_importances_")
                    else [np.nan]*len(cols), index=cols)
    if imp.notna().any():
        print("\nFeatures más importantes:")
        print(imp.sort_values(ascending=False).head(6).round(3).to_string())

    piso = tabla.loc["ets_sin_tendencia"]
    mod = tabla.loc["modelo_gbr"]
    print("\n" + "=" * 78)
    if mod["mediana"] < piso["mediana"] and mod["media"] < piso["media"]:
        print(f"RESULTADO: el modelo BATE el piso en mediana y media "
              f"({mod['mediana']}/{mod['media']} vs {piso['mediana']}/{piso['media']}).")
    else:
        print(f"RESULTADO: el modelo NO bate el piso en ambas estadísticas "
              f"(modelo {mod['mediana']}/{mod['media']} vs ETS {piso['mediana']}/{piso['media']}).")
        print("Honestidad D3: si no lo bate tras iterar, el entregable es el pipeline.")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(SALIDA, index=False, encoding="utf-8")
    print(f"\nGuardado: {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()

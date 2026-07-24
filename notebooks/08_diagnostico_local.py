"""
Fase 4 · Diagnóstico D3b: transferibilidad nacional vs. solo-Mérida.

Responde la pregunta de D2/D3b: ¿el modelo nacional le sirve a Mérida, o Mérida
es idiosincrática y el pooling le mete ruido? Comparación justa: misma métrica,
mismos 12 meses de prueba de Mérida, mismo denominador MASE. Lo ÚNICO que cambia
es de qué aprende cada modelo.

  - Nacional: el modelo ya entrenado (07) sobre los 316 municipios; su MASE de
    Mérida ya está en modelo_vs_baseline.csv (Mérida fue held-out también para él).
  - Solo-Mérida: un HistGBR entrenado ÚNICAMENTE con los pares (origen, horizonte)
    de Mérida (~cientos de filas), con hiperparámetros apropiados a ese tamaño
    (regularización más suave; usar la del nacional lo dejaría casi constante y
    sería una comparación amañada en su contra).

ADVERTENCIA DE INTERPRETACIÓN (declarada antes de ver el número, para no
racionalizar después): con tan pocos datos de entrenamiento, el solo-Mérida puede
perder por FALTA DE DATOS, no porque el pooling capture mejor la dinámica. Si el
nacional gana, no distingue por sí solo entre "el pooling ayuda" y "Mérida sola no
alcanza". Y es una sola ventana de prueba (n=1): el veredicto es sugerente, no
definitivo. Un backtest de origen móvil (retrenando en cada origen) sería la
versión robusta, y es el paso siguiente si el resultado es ajustado o importante.

Entrada: data/interim/features.csv, data/interim/panel_modelado.csv,
         data/processed/modelo_vs_baseline.csv, data/processed/baselines_por_municipio.csv
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402

FEATS = RAIZ / "data" / "interim" / "features.csv"
PANEL = RAIZ / "data" / "interim" / "panel_modelado.csv"
MODELO = RAIZ / "data" / "processed" / "modelo_vs_baseline.csv"
BASE = RAIZ / "data" / "processed" / "baselines_por_municipio.csv"
LLAVE = ["estado", "clave_municipio"]
H = 12
NO_FEATURES = set(LLAVE + ["origen_fecha", "objetivo_fecha", "y", "split"])

# Mérida = estado 31, municipio 050. Configurable para pruebas.
OBJETIVO_ESTADO = 31
OBJETIVO_CLAVE = 50


def escala_mase(serie_acciones: np.ndarray) -> float | None:
    y = np.asarray(serie_acciones, dtype=float)
    yt = y[:-H]
    if len(yt) <= 12:
        return None
    d = float(np.mean(np.abs(yt[12:] - yt[:-12])))
    return d if d > 0 else None


def main(est=OBJETIVO_ESTADO, clave=OBJETIVO_CLAVE):
    for p in (FEATS, PANEL, MODELO, BASE):
        if not p.exists():
            raise SystemExit(f"Falta {p}. Corre las fases previas (06, 07).")
    feats = pd.read_csv(FEATS, parse_dates=["origen_fecha", "objetivo_fecha"])
    panel = pd.read_csv(PANEL, parse_dates=["fecha"])
    mvb = pd.read_csv(MODELO)
    base = pd.read_csv(BASE)

    cols = [c for c in feats.columns if c not in NO_FEATURES]
    sel = (feats["estado"] == est) & (feats["clave_municipio"] == clave)
    loc = feats[sel]
    if loc.empty:
        raise SystemExit(f"El municipio {est}/{clave} no está en features.")

    tr_loc = loc[loc["split"] == "train"]
    te_loc = loc[loc["split"] == "test"].sort_values("objetivo_fecha")

    # escala MASE del municipio (idéntica a 05/07)
    s = panel[(panel["estado"] == est) & (panel["clave_municipio"] == clave)]
    esc = escala_mase(s.sort_values("fecha")["acciones"].to_numpy())
    if esc is None:
        raise SystemExit("Escala MASE indefinida para el municipio.")

    # --- modelo SOLO-MÉRIDA: hiperparámetros apropiados al tamaño ---
    print(f"Solo-{est}/{clave}: {len(tr_loc)} filas de entrenamiento "
          f"(vs 403k del nacional).")
    m_loc = HistGradientBoostingRegressor(
        loss="absolute_error", learning_rate=0.05, max_iter=300,
        max_leaf_nodes=15, min_samples_leaf=20, random_state=0)
    m_loc.fit(tr_loc[cols], tr_loc["y"])
    pred_loc = np.clip(m_loc.predict(te_loc[cols]), 0, None)
    mase_local = float(np.mean(np.abs(te_loc["y"].to_numpy() - pred_loc))) / esc

    # --- nacional: leer su MASE ya computado para este municipio ---
    fila_nac = mvb[(mvb["estado"] == est) & (mvb["clave_municipio"] == clave)]
    mase_nacional = float(fila_nac["mase_modelo"].iloc[0]) if len(fila_nac) else np.nan

    # --- baselines del municipio, como referencia ---
    fila_b = base[(base["estado"] == est) & (base["clave_municipio"] == clave)]
    def bval(c):
        return float(fila_b[c].iloc[0]) if len(fila_b) and c in fila_b else np.nan

    print("\n" + "=" * 70)
    print(f"DIAGNÓSTICO D3b — MASE sobre Mérida ({est}/{clave}), holdout 12 meses")
    print("-" * 70)
    tabla = pd.DataFrame({
        "MASE": {
            "modelo_nacional": round(mase_nacional, 3),
            "modelo_solo_merida": round(mase_local, 3),
            "ets_sin_tendencia": round(bval("mase_ets_sin_tendencia"), 3),
            "seasonal_naive": round(bval("mase_seasonal_naive"), 3),
        }})
    print(tabla.to_string())

    print("\n" + "=" * 70)
    if np.isnan(mase_nacional):
        print("No se encontró el MASE nacional de Mérida en modelo_vs_baseline.csv.")
    elif mase_nacional <= mase_local:
        print(f"RESULTADO: el NACIONAL gana o empata en Mérida "
              f"({mase_nacional:.3f} <= {mase_local:.3f}).")
        print("El pooling le sirve a Mérida — D2 se sostiene. PERO ver la")
        print("advertencia: podría ser falta de datos del solo-Mérida, no")
        print("superioridad del pooling. Backtest de origen móvil para confirmar.")
    else:
        print(f"RESULTADO: el SOLO-MÉRIDA gana ({mase_local:.3f} < {mase_nacional:.3f}).")
        print("Mérida es idiosincrática: el pooling le mete ruido. Considerar")
        print("modelo regional/local para el despliegue. Hallazgo, no fracaso.")


if __name__ == "__main__":
    main()

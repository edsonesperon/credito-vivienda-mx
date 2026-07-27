"""
Fase 4 · Tracking de experimentos con MLflow (local, sin servidor).

Registra las corridas en ./mlflow.db + ./mlartifacts (ignorados por git), sin servidor ni base de
datos — el 90% del valor con el 10% de la complejidad (D5). El registry y el
servidor entran cuando exista el servicio (fase 5), no antes.

Qué hace:
  - Corrida del MODELO: entrena el HistGBR (misma especificación que 07) dentro de
    un run de MLflow, y registra parámetros, métricas (MASE) y el modelo como
    ARTEFACTO versionado, con firma de entrada/salida.
  - Corridas de BASELINES: registra el MASE de cada baseline (de 05) como runs
    aparte del mismo experimento, para poder compararlos lado a lado en la UI.

Ver los experimentos:  mlflow ui   (y abrir http://127.0.0.1:5000)

Entrada: data/interim/features.csv, data/interim/panel_modelado.csv,
         data/processed/baselines_resumen.csv
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
import mlflow  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from mlflow.models import infer_signature  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402

FEATS = RAIZ / "data" / "interim" / "features.csv"
PANEL = RAIZ / "data" / "interim" / "panel_modelado.csv"
BASE_RES = RAIZ / "data" / "processed" / "baselines_resumen.csv"
LLAVE = ["estado", "clave_municipio"]
H = 12
NO_FEATURES = set(LLAVE + ["origen_fecha", "objetivo_fecha", "y", "split"])
EXPERIMENTO = "demanda-credito-vivienda"

PARAMS_MODELO = dict(loss="absolute_error", learning_rate=0.05, max_iter=400,
                     max_leaf_nodes=31, min_samples_leaf=100, random_state=0)


def escala_mase(serie):
    y = np.asarray(serie, dtype=float)
    yt = y[:-H]
    if len(yt) <= 12:
        return None
    d = float(np.mean(np.abs(yt[12:] - yt[:-12])))
    return d if d > 0 else None


def evaluar(te, panel):
    escalas = {k: escala_mase(g.sort_values("fecha")["acciones"].to_numpy())
               for k, g in panel.groupby(LLAVE)}
    vals = []
    for llave, g in te.groupby(LLAVE):
        esc = escalas.get(llave)
        if esc:
            vals.append(float(np.mean(np.abs(g["y"] - g["pred"]))) / esc)
    v = pd.Series(vals)
    return {"mase_mediana": float(v.median()), "mase_media": float(v.mean()),
            "mase_p90": float(v.quantile(0.90)), "pct_mase_menor_1": float((v < 1).mean()),
            "municipios": int(len(v))}


def main():
    for p in (FEATS, PANEL, BASE_RES):
        if not p.exists():
            raise SystemExit(f"Falta {p}. Corre las fases previas.")
    feats = pd.read_csv(FEATS, parse_dates=["origen_fecha", "objetivo_fecha"])
    panel = pd.read_csv(PANEL, parse_dates=["fecha"])
    base = pd.read_csv(BASE_RES)

    cols = [c for c in feats.columns if c not in NO_FEATURES]
    tr = feats[feats["split"] == "train"]
    te = feats[feats["split"] == "test"].copy()

    # MLflow 3.x dejó el file store en modo mantenimiento; se usa SQLite, que
    # sigue siendo local y de un solo archivo (sin servidor ni base de datos
    # remota — coherente con D5). Los artefactos van a ./mlartifacts.
    mlflow.set_tracking_uri(f"sqlite:///{RAIZ / 'mlflow.db'}")
    exp = mlflow.get_experiment_by_name(EXPERIMENTO)
    if exp is None:
        mlflow.create_experiment(
            EXPERIMENTO, artifact_location=f"file:{RAIZ / 'mlartifacts'}")
    mlflow.set_experiment(EXPERIMENTO)

    # --- corrida del modelo ---
    with mlflow.start_run(run_name="modelo_gbr_global") as run:
        mlflow.log_params(PARAMS_MODELO)
        mlflow.log_params({"target": "acciones", "n_features": len(cols),
                           "n_train": len(tr), "horizonte_max": H,
                           "corte_train": str(te["origen_fecha"].iloc[0].date())})
        modelo = HistGradientBoostingRegressor(**PARAMS_MODELO)
        modelo.fit(tr[cols], tr["y"])
        te["pred"] = np.clip(modelo.predict(te[cols]), 0, None)
        metricas = evaluar(te, panel)
        mlflow.log_metrics(metricas)
        firma = infer_signature(tr[cols].head(), modelo.predict(tr[cols].head()))
        mlflow.sklearn.log_model(modelo, name="modelo", signature=firma,
                                 input_example=tr[cols].head(3))
        mlflow.set_tag("fase", "4")
        print(f"Modelo registrado: MASE mediana {metricas['mase_mediana']:.3f}, "
              f"media {metricas['mase_media']:.3f}  (run {run.info.run_id[:8]})")

    # --- corridas de baselines (de 05), para comparar en la UI ---
    acc = base[base["target"] == "acciones"]
    for _, r in acc.iterrows():
        with mlflow.start_run(run_name=f"baseline_{r['metodo']}"):
            mlflow.log_param("metodo", r["metodo"])
            mlflow.log_param("target", "acciones")
            mlflow.log_metrics({"mase_mediana": float(r["mase_mediana"]),
                                "mase_media": float(r["mase_media"]),
                                "mase_p90": float(r["mase_p90"]),
                                "pct_mase_menor_1": float(r["pct_mase<1"]) / 100})
            mlflow.set_tag("fase", "3")
    print(f"Baselines registrados: {len(acc)} runs")

    print(f"\nExperimento '{EXPERIMENTO}' en {RAIZ / 'mlruns'}")
    print("Para ver los experimentos lado a lado:  mlflow ui")


if __name__ == "__main__":
    main()

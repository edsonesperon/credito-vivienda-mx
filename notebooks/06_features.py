"""
Fase 4 · Construcción de features para el modelo global directo.

Cada fila de entrenamiento es un par (origen, horizonte): "parado en el mes t0,
predice el mes t0+h". El modelo es uno solo; h entra como feature.

ANTI-FUGA POR CONSTRUCCIÓN (no por disciplina de recordarlo):
    TODAS las features de la serie en el origen t0 se calculan con shift/rolling/
    expanding hacia atrás — solo tocan valores en posiciones <= t0. El objetivo
    y[t0+h] es estrictamente futuro. Por diseño, ninguna feature puede depender de
    un valor posterior al origen. Se verifica con una prueba que perturba un valor
    futuro y confirma que las features del origen no cambian (test_antifuga).

    El calendario es del mes OBJETIVO (t0+h), no del origen: saber que el mes que
    predigo es diciembre es determinista y legítimo, no fuga.

Features:
    serie (desde el origen): lag_1..lag_3, lag_12; media móvil 3/6/12; desv 3/6
    contexto del municipio (hasta el origen): media histórica, desv histórica,
        ticket medio histórico  -> describen "quién es" el municipio sin nombrarlo
        (coherente con D2: aíslan el nivel para que el modelo comparta la dinámica)
    calendario del objetivo: mes_num, trimestre
    horizonte: h

Partición temporal (comparable al piso de baselines):
    train  = pares cuyo mes objetivo <= 2025-04
    test   = origen 2025-04, h=1..12  -> objetivos 2025-05..2026-04
    Mismo origen y mismos 12 meses que evaluaron los baselines: comparación justa.

Entrada: data/interim/panel_modelado.csv
Salida:  data/interim/features.csv  (con columna split: train/test)
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

PANEL = RAIZ / "data" / "interim" / "panel_modelado.csv"
SALIDA = RAIZ / "data" / "interim" / "features.csv"
LLAVE = ["estado", "clave_municipio"]
TARGET = "acciones"
H_MAX = 12
CORTE_TRAIN = pd.Timestamp("2025-04-01")   # último mes objetivo del train


def features_por_origen(y: np.ndarray) -> pd.DataFrame:
    """Matriz de features del ORIGEN por posición t. Cada fila usa solo y[0..t]."""
    s = pd.Series(y, dtype=float)
    f = pd.DataFrame(index=s.index)
    for k in (1, 2, 3, 12):
        f[f"lag_{k}"] = s.shift(k - 1)          # lag_1 = y[t] (último conocido)
    for w in (3, 6, 12):
        f[f"rmean_{w}"] = s.rolling(w).mean()   # ventana termina en t
    for w in (3, 6):
        f[f"rstd_{w}"] = s.rolling(w).std()
    f["hist_mean"] = s.expanding().mean()       # nivel del municipio hasta t
    f["hist_std"] = s.expanding().std()
    return f


def construir(df: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for llave, g in df.groupby(LLAVE):
        g = g.sort_values("fecha").reset_index(drop=True)
        y = g[TARGET].to_numpy(dtype=float)
        tk = (g["monto"] / g[TARGET].replace(0, np.nan)).to_numpy()  # ticket
        fechas = g["fecha"].to_numpy()
        fo = features_por_origen(y)
        hist_ticket = pd.Series(tk).expanding().mean().to_numpy()
        n = len(g)
        for t0 in range(n):
            if pd.isna(fo["lag_12"].iloc[t0]):     # exige historia para lag_12
                continue
            base = fo.iloc[t0].to_dict()
            base["hist_ticket"] = hist_ticket[t0]
            for h in range(1, H_MAX + 1):
                if t0 + h >= n:
                    continue
                objetivo_fecha = pd.Timestamp(fechas[t0 + h])
                fila = dict(base)
                fila.update({
                    "estado": llave[0], "clave_municipio": llave[1],
                    "origen_fecha": pd.Timestamp(fechas[t0]),
                    "objetivo_fecha": objetivo_fecha,
                    "h": h,
                    "mes_num": objetivo_fecha.month,
                    "trimestre": (objetivo_fecha.month - 1) // 3 + 1,
                    "y": y[t0 + h],
                })
                filas.append(fila)
    out = pd.DataFrame(filas)
    out["split"] = np.where(out["objetivo_fecha"] <= CORTE_TRAIN, "train", "test")
    # el test se restringe al origen del último mes de train, para igualar a los baselines
    es_test = (out["split"] == "test") & (out["origen_fecha"] == CORTE_TRAIN)
    out = out[(out["split"] == "train") | es_test].reset_index(drop=True)
    return out


def main():
    if not PANEL.exists():
        raise SystemExit("Falta data/interim/panel_modelado.csv. Corre antes 04.")
    df = pd.read_csv(PANEL, parse_dates=["fecha"])
    feats = construir(df)

    tr = feats[feats["split"] == "train"]
    te = feats[feats["split"] == "test"]
    cols_feat = [c for c in feats.columns if c not in
                 (*LLAVE, "origen_fecha", "objetivo_fecha", "y", "split")]

    print("FEATURES PARA EL MODELO GLOBAL DIRECTO")
    print(f"  filas train : {len(tr)}  (objetivo <= {CORTE_TRAIN:%Y-%m})")
    print(f"  filas test  : {len(te)}  (origen {CORTE_TRAIN:%Y-%m}, h=1..12)")
    print(f"  municipios en test: {te.groupby(LLAVE).ngroups}")
    print(f"  features ({len(cols_feat)}): {cols_feat}")
    print(f"  nulos en features de train: {int(tr[cols_feat].isna().sum().sum())}")
    print(f"  rango objetivo test: {te['objetivo_fecha'].min():%Y-%m} a {te['objetivo_fecha'].max():%Y-%m}")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    feats.to_csv(SALIDA, index=False, encoding="utf-8")
    print(f"\nGuardado: {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()

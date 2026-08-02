"""
Fase 5 · API del Observatorio de Vivienda Financiada.

Sirve las predicciones pre-computadas (10_predicciones.py): el pronóstico de
demanda de crédito de adquisición por municipio, a 12 meses. La API NO reentrena
ni recalcula features — solo consulta la tabla, así que es rápida y sin superficie
de error de modelado en tiempo de respuesta.

Levantar:  uvicorn api.main:app --reload    (desde la raíz del repo)
Docs interactivas:  http://127.0.0.1:8000/docs

Endpoints:
  GET /                         info y salud
  GET /municipios               catálogo de municipios con pronóstico
  GET /prediccion/{estado}/{clave}          pronóstico de 12 meses
  GET /prediccion/{estado}/{clave}?h=3      un horizonte específico
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

RAIZ = Path(__file__).resolve().parents[1]
PRED = RAIZ / "data" / "processed" / "predicciones.csv"

app = FastAPI(
    title="Observatorio de Vivienda Financiada",
    description="Pronóstico municipal de demanda de crédito de adquisición (Infonavit).",
    version="0.1.0",
)

_pred: pd.DataFrame | None = None


def predicciones() -> pd.DataFrame:
    """Carga perezosa y cacheada de la tabla de pronóstico."""
    global _pred
    if _pred is None:
        if not PRED.exists():
            raise HTTPException(503, "Predicciones no disponibles. Corre 10_predicciones.py.")
        _pred = pd.read_csv(PRED)
    return _pred


@app.get("/")
def raiz():
    df = predicciones()
    return {
        "servicio": "Observatorio de Vivienda Financiada",
        "estado": "activo",
        "municipios": int(df.groupby(["estado", "clave_municipio"]).ngroups),
        "origen_pronostico": str(df["origen_fecha"].iloc[0]),
        "horizonte_meses": int(df["h"].max()),
        "docs": "/docs",
    }


@app.get("/municipios")
def municipios():
    df = predicciones()
    cat = (df[["estado", "clave_municipio", "municipio"]]
           .drop_duplicates()
           .sort_values(["estado", "clave_municipio"]))
    return {"total": len(cat), "municipios": cat.to_dict(orient="records")}


@app.get("/prediccion/{estado}/{clave}")
def prediccion(estado: int, clave: int,
               h: int | None = Query(None, ge=1, le=12,
                                     description="Horizonte 1-12; omitir para los 12 meses")):
    df = predicciones()
    sel = df[(df["estado"] == estado) & (df["clave_municipio"] == clave)]
    if sel.empty:
        raise HTTPException(404, f"Municipio {estado}/{clave} no está en el pronóstico. "
                                 f"Ver /municipios para el catálogo.")
    if h is not None:
        sel = sel[sel["h"] == h]
        if sel.empty:
            raise HTTPException(404, f"Horizonte {h} no disponible.")

    meses = [{"mes": r["objetivo_fecha"], "horizonte": int(r["h"]),
              "prediccion_acciones": int(r["prediccion_acciones"])}
             for _, r in sel.sort_values("h").iterrows()]
    fila = sel.iloc[0]
    return {
        "estado": int(fila["estado"]),
        "clave_municipio": int(fila["clave_municipio"]),
        "municipio": fila["municipio"],
        "origen": str(fila["origen_fecha"]),
        "pronostico": meses,
    }

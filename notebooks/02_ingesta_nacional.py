"""
Fase 2 · Ingesta nacional del panel INFONAVIT (mensual, municipal).

Jala el panel mensual municipal de las 32 entidades y lo guarda CRUDO con su
procedencia. No filtra ni analiza aquí: la separación es deliberada — el pull es
lento y toca la red; el análisis (03) es local y se re-corre barato. No se
re-jala para re-analizar.

Dimensiones (todas confirmadas reales en 01_validacion_v2):
    anio, municipio, mes, valor_vivienda, modalidad
    `clave_municipio` viene gratis en la respuesta (llave INEGI para joins).

Salida:
    data/raw/panel_infonavit_nacional.csv
    data/raw/panel_infonavit_nacional.procedencia.json
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import pandas as pd  # noqa: E402

from ingesta_sniiv import ESTADOS, ErrorConsultaSNIIV, consultar, normalizar_filas  # noqa: E402

ORGANISMO = "infonavit"
ANIOS = list(range(2015, 2027))
DIMENSIONES = ("anio", "municipio", "mes", "valor_vivienda", "modalidad")
SALIDA = RAIZ / "data" / "raw" / "panel_infonavit_nacional.csv"


def jalar_estado(estado: str, timeout: float = 90.0) -> list[dict]:
    """Un estado, todos los años, todas las dimensiones. Filas normalizadas,
    con `estado` de procedencia añadido."""
    crudas = consultar(ORGANISMO, ANIOS, estado, "000", DIMENSIONES, timeout=timeout)
    filas = normalizar_filas(crudas, DIMENSIONES)
    for f in filas:
        f["estado"] = estado
    return filas


def jalar_nacional(estados=ESTADOS, pausa: float = 0.7):
    """Itera las 32 entidades. Una incidencia en un estado no aborta el resto:
    se registra y se continúa. Un estado caído es información, no un fallo fatal."""
    filas: list[dict] = []
    incidencias: list[dict] = []
    for i, est in enumerate(estados, 1):
        try:
            fs = jalar_estado(est)
            filas.extend(fs)
            print(f"  [{i:2d}/{len(estados)}] estado {est}: {len(fs):>7} filas")
        except ErrorConsultaSNIIV as exc:
            incidencias.append({"estado": est, "error": str(exc)[:200]})
            print(f"  [{i:2d}/{len(estados)}] estado {est}: ERROR -> {str(exc)[:90]}")
        time.sleep(pausa)
    return filas, incidencias


def main():
    print(f"Ingesta nacional INFONAVIT · {len(ANIOS)} años · dims {DIMENSIONES}")
    print("Esto tarda: ~32 consultas con pausa. No lo interrumpas.\n")
    t0 = time.time()

    filas, incidencias = jalar_nacional()
    df = pd.DataFrame(filas)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SALIDA, index=False, encoding="utf-8")

    procedencia = {
        "fuente": "SNIIV CuboAPI — GetINFONAVIT",
        "organismo": ORGANISMO,
        "dimensiones_solicitadas": list(DIMENSIONES),
        "rango_anios": [ANIOS[0], ANIOS[-1]],
        "fecha_extraccion_utc": datetime.now(timezone.utc).isoformat(),
        "n_filas": int(len(df)),
        "columnas_devueltas": list(df.columns),
        "estados_ok": len(ESTADOS) - len(incidencias),
        "incidencias": incidencias,
        "nota_trampas": ("modalidad mezcla adquisición/mejora/pasivos/suelo; "
                         "filtrar en 03. valor_vivienda incluye 'No disponible'. "
                         "Autoconstrucción y Ampliación traen monto atípico o 0."),
    }
    SALIDA.with_suffix(".procedencia.json").write_text(
        json.dumps(procedencia, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nGuardado: {SALIDA.name}  ({len(df)} filas, {time.time()-t0:.0f}s)")
    print(f"Columnas devueltas: {list(df.columns)}")
    if incidencias:
        print(f"\n⚠ {len(incidencias)} incidencia(s) — ver .procedencia.json y tráemelas.")
    else:
        print("Sin incidencias: los 32 estados respondieron.")


if __name__ == "__main__":
    main()

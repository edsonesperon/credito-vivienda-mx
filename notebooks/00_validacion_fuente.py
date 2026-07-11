"""
Arnés de validación empírica de la CuboAPI del SNIIV.

CÓRRELO LOCALMENTE: necesita alcanzar sniiv.sedatu.gob.mx (este repositorio se
diseñó sin asumir nada de la API; esto es lo que convierte suposiciones en hechos).
Puede ejecutarse como script (`python notebooks/00_validacion_fuente.py`) o
pegarse por bloques en un notebook de JupyterLab.

Cada función DERIVA su resultado de la respuesta real. Ninguna afirma de antemano
qué años hay, qué dimensiones existen ni cuál es el token de segmento. Al final
imprime un reporte que responde, con evidencia, la bitácora de decisiones
abiertas del docs/vision.md:

  1. ¿La API acepta `mes`?                        -> probar_dimensiones()
  2. ¿Hasta qué año hay datos?                     -> probar_anios()
  3. ¿Se separa adquisición de mejoramiento?       -> probar_dimensiones() (modalidad/tipo_credito)
  4. ¿Cuál es el tope de dimensiones?              -> probar_tope_dimensiones()
  5. Dispersión de Mérida / municipios chicos      -> perfilar_cobertura()
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from ingesta_sniiv import (  # noqa: E402
    ErrorConsultaSNIIV,
    consultar,
    normalizar_filas,
)

YUCATAN = "31"
MERIDA = "050"

# Combinación CONFIRMADA como válida para INFONAVIT por el ejemplo oficial.
DIMS_CONFIRMADAS = ("anio", "municipio", "genero")

# Dimensiones CANDIDATAS a probar. No se afirma que existan: aparecieron en
# ejemplos de distintos organismos (segmento_uma, valor_vivienda, modalidad,
# rango_edad, genero, tipo_vivienda, poblacion_indigena) o son hipótesis
# razonables (mes, segmento, tipo_credito, producto, destino). La API dictamina.
DIMS_CANDIDATAS = (
    "mes",
    "segmento",
    "segmento_uma",
    "valor_vivienda",
    "modalidad",
    "tipo_credito",
    "producto",
    "destino",
    "rango_edad",
    "tipo_vivienda",
)


def probar_anios(
    organismo: str = "infonavit",
    estado: str = YUCATAN,
    desde: int = 2015,
    hasta: int | None = None,
) -> pd.DataFrame:
    """Consulta año por año y reporta cuántas filas/acciones devuelve cada uno.
    Un año con 0 filas o error => no cargado. Determina el último año disponible.
    """
    hasta = hasta or date.today().year
    reporte = []
    for anio in range(desde, hasta + 1):
        try:
            crudas = consultar(organismo, anio, estado, "000", ("anio", "municipio"))
            filas = normalizar_filas(crudas, ("anio", "municipio"))
            acciones = sum((f.get("acciones") or 0) for f in filas)
            reporte.append({"anio": anio, "filas": len(filas), "acciones": acciones,
                            "estatus": "ok" if filas else "vacio"})
        except ErrorConsultaSNIIV as exc:
            reporte.append({"anio": anio, "filas": 0, "acciones": 0,
                            "estatus": f"error: {str(exc)[:80]}"})
    return pd.DataFrame(reporte)


def probar_dimensiones(
    organismo: str = "infonavit",
    anio: int = 2020,
    estado: str = YUCATAN,
    candidatas: tuple[str, ...] = DIMS_CANDIDATAS,
) -> pd.DataFrame:
    """Para cada dimensión candidata, intenta `anio,municipio,<candidata>` y
    reporta si la API la aceptó, cuántas filas y una muestra de valores distintos.
    Así se descubre si existe `mes`, cuál es el token real de segmento, y si hay
    una dimensión que separe adquisición de mejoramiento.
    """
    reporte = []
    for dim in candidatas:
        dims = ("anio", "municipio", dim)
        try:
            crudas = consultar(organismo, anio, estado, "000", dims)
            filas = normalizar_filas(crudas, dims)
            valores = sorted({str(f.get(dim)) for f in filas if f.get(dim) is not None})
            reporte.append({
                "dimension": dim,
                "aceptada": bool(filas),
                "filas": len(filas),
                "valores_muestra": valores[:8],
                "n_valores": len(valores),
            })
        except ErrorConsultaSNIIV as exc:
            reporte.append({"dimension": dim, "aceptada": False, "filas": 0,
                            "valores_muestra": [], "n_valores": 0,
                            "error": str(exc)[:80]})
    return pd.DataFrame(reporte)


def probar_tope_dimensiones(
    organismo: str = "infonavit",
    anio: int = 2020,
    estado: str = YUCATAN,
    base: tuple[str, ...] = ("anio", "estado", "municipio", "genero"),
    extra: tuple[str, ...] = ("rango_edad", "tipo_vivienda"),
) -> pd.DataFrame:
    """Agrega dimensiones de a una hasta que la API falla, para encontrar el tope
    real (en los ejemplos oficiales el máximo observado es 5, pero es inferencia)."""
    reporte = []
    dims = list(base)
    for extra_dim in ("",) + extra:
        prueba = dims + ([extra_dim] if extra_dim else [])
        try:
            crudas = consultar(organismo, anio, estado, "000", prueba)
            reporte.append({"n_dimensiones": len(prueba), "dims": prueba,
                            "ok": True, "filas": len(crudas)})
        except ErrorConsultaSNIIV as exc:
            reporte.append({"n_dimensiones": len(prueba), "dims": prueba,
                            "ok": False, "error": str(exc)[:80]})
        if extra_dim:
            dims = prueba
    return pd.DataFrame(reporte)


def perfilar_cobertura(
    organismo: str = "infonavit",
    estado: str = YUCATAN,
    municipio: str = MERIDA,
    desde: int = 2015,
    hasta: int | None = None,
    dim_segmento: str | None = None,
) -> pd.DataFrame:
    """Perfila la dispersión de un municipio: años presentes, y si se da un token
    de segmento válido, el desglose por año×segmento con celdas vacías/None.
    `dim_segmento` NO se asume: pásalo con lo que probar_dimensiones() confirme.
    """
    hasta = hasta or date.today().year
    anios = list(range(desde, hasta + 1))
    dims = ("anio", "segmento") if dim_segmento is None else ("anio", dim_segmento)
    if dim_segmento is None:
        dims = ("anio",)
    try:
        crudas = consultar(organismo, anios, estado, municipio, dims)
    except ErrorConsultaSNIIV as exc:
        print(f"  perfilar_cobertura falló: {exc}")
        return pd.DataFrame()
    df = pd.DataFrame(normalizar_filas(crudas, dims))
    if df.empty:
        return df
    df["acciones_nulas"] = df["acciones"].isna()
    return df


def _imprimir(titulo: str, df: pd.DataFrame) -> None:
    print("\n" + "=" * 70 + f"\n{titulo}\n" + "-" * 70)
    if df is None or df.empty:
        print("  (sin datos)")
    else:
        with pd.option_context("display.max_columns", None, "display.width", 120):
            print(df.to_string(index=False))


def main() -> None:
    print("VALIDACIÓN EMPÍRICA DE LA FUENTE SNIIV — organismo: INFONAVIT")
    print("Todo lo de abajo sale de respuestas reales de la API, no de supuestos.")

    df_anios = probar_anios()
    _imprimir("1/5 · Años con datos (Yucatán)", df_anios)

    disponibles = df_anios.loc[df_anios["estatus"] == "ok", "anio"]
    anio_ref = int(disponibles.max()) if not disponibles.empty else 2020
    print(f"\n-> último año con datos detectado: {anio_ref} (se usa como referencia)")

    df_dims = probar_dimensiones(anio=anio_ref)
    _imprimir(f"2/5 · Dimensiones aceptadas (año {anio_ref})", df_dims)

    df_tope = probar_tope_dimensiones(anio=anio_ref)
    _imprimir("3/5 · Tope de dimensiones por consulta", df_tope)

    # Para el perfil por segmento, usa el primer token de segmento que la API haya
    # aceptado; si ninguno, perfila solo por año.
    seg_tokens = {"segmento", "segmento_uma", "valor_vivienda"}
    aceptadas = set(df_dims.loc[df_dims["aceptada"], "dimension"]) if not df_dims.empty else set()
    dim_seg = next((t for t in ("segmento", "segmento_uma", "valor_vivienda")
                    if t in aceptadas), None)
    print(f"\n-> token de segmento a usar en el perfil: {dim_seg!r}")

    df_merida = perfilar_cobertura(hasta=anio_ref, dim_segmento=dim_seg)
    _imprimir("4/5 · Cobertura y dispersión de Mérida", df_merida)

    print("\n" + "=" * 70)
    print("5/5 · Lectura para la bitácora (docs/vision.md §11):")
    print(f"  - ¿`mes` existe? -> {'SÍ' if 'mes' in aceptadas else 'NO (granularidad anual)'}")
    print(f"  - último año cargado -> {anio_ref}")
    print(f"  - token de segmento -> {dim_seg or 'ninguno aceptado'}")
    sep = aceptadas & {"modalidad", "tipo_credito", "producto", "destino"}
    print(f"  - separa adquisición/mejoramiento vía -> {sep or 'sin dimensión que lo permita (revisar manualmente)'}")
    print("  - tope de dimensiones -> ver tabla 3/5")
    print("\nEstos hallazgos se copian a docs/vision.md antes de escribir el pull nacional.")


if __name__ == "__main__":
    main()

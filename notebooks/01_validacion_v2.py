"""
Validación v2 de la fuente SNIIV — corrige los defectos de la v1.

Qué corrige:
  - v1 declaraba "aceptada" toda dimensión que devolviera filas. Pero la API
    IGNORA en silencio las dimensiones que no conoce, así que todo salía True.
    v2 compara las LLAVES CRUDAS de la respuesta contra un baseline: si aparece
    una llave nueva, la dimensión existe y esa llave es su nombre real.
  - v1 no medía la dispersión mensual ni descomponía por modalidad.

Qué resuelve:
  1. Nombre real del campo que devuelve `rango_edad` (existe pero con otro nombre).
  2. Tope de dimensiones, usando solo dimensiones REALES.
  3. Dispersión municipio-mes: decide si la unidad de análisis es mensual o anual.
  4. Descomposición de Mérida por modalidad: prueba si el ticket sube al filtrar
     a adquisición (Nueva + Existente).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from ingesta_sniiv import ErrorConsultaSNIIV, consultar, normalizar_filas  # noqa: E402

YUCATAN = "31"
MERIDA = "050"
ANIO_REF = 2025          # último año COMPLETO (2026 va a abril)
ANIOS = list(range(2015, 2027))

# Confirmadas reales en la v1 (aumentaron filas Y trajeron valores)
DIMS_REALES = ("mes", "valor_vivienda", "modalidad", "tipo_credito", "genero")
# Sospechosas de fantasma o de nombre renombrado
DIMS_SOSPECHOSAS = ("rango_edad", "segmento", "segmento_uma", "producto",
                    "destino", "tipo_vivienda", "edad", "grupo_edad", "uma",
                    "ingreso", "nivel_ingreso")


def _llaves(filas: list[dict]) -> set[str]:
    llaves: set[str] = set()
    for f in filas:
        llaves |= set(f.keys())
    return llaves


def descubrir_dimensiones(candidatas, anio=ANIO_REF, estado=YUCATAN):
    """Compara las llaves crudas contra el baseline `anio,municipio`.
    Llave nueva => la dimensión existe, y esa llave es su NOMBRE REAL."""
    base = consultar("infonavit", anio, estado, "000", ("anio", "municipio"))
    llaves_base = _llaves(base)
    print(f"  llaves del baseline: {sorted(llaves_base)}  ({len(base)} filas)\n")

    reporte = []
    for dim in candidatas:
        try:
            crudas = consultar("infonavit", anio, estado, "000",
                               ("anio", "municipio", dim))
            nuevas = _llaves(crudas) - llaves_base
            valores = []
            if nuevas:
                k = sorted(nuevas)[0]
                valores = sorted({str(f.get(k)) for f in crudas if f.get(k)})
            reporte.append({
                "dimension_pedida": dim,
                "existe": bool(nuevas),
                "llave_real": ", ".join(sorted(nuevas)) or "—",
                "filas": len(crudas),
                "n_valores": len(valores),
                "valores": valores[:8],
            })
        except ErrorConsultaSNIIV as exc:
            reporte.append({"dimension_pedida": dim, "existe": False,
                            "llave_real": f"ERROR: {str(exc)[:50]}",
                            "filas": 0, "n_valores": 0, "valores": []})
    return pd.DataFrame(reporte)


def probar_tope(anio=ANIO_REF, estado=YUCATAN):
    """Agrega dimensiones REALES de a una; el tope es donde deja de aparecer
    una llave nueva (o donde la API falla)."""
    reporte = []
    acumuladas = ["anio", "municipio"]
    base = consultar("infonavit", anio, estado, "000", acumuladas)
    llaves_prev = _llaves(base)
    for dim in DIMS_REALES:
        acumuladas = acumuladas + [dim]
        try:
            crudas = consultar("infonavit", anio, estado, "000", acumuladas)
            nuevas = _llaves(crudas) - llaves_prev
            reporte.append({"n_dims": len(acumuladas), "agregada": dim,
                            "llave_nueva": ", ".join(sorted(nuevas)) or "NINGUNA",
                            "se_aplico": bool(nuevas), "filas": len(crudas)})
            llaves_prev |= nuevas
        except ErrorConsultaSNIIV as exc:
            reporte.append({"n_dims": len(acumuladas), "agregada": dim,
                            "llave_nueva": f"ERROR: {str(exc)[:50]}",
                            "se_aplico": False, "filas": 0})
            break
    return pd.DataFrame(reporte)


def dispersion_mensual(estado=YUCATAN, anios=ANIOS):
    """¿Cuántas celdas municipio-mes existen realmente? La API solo devuelve
    celdas con dato, así que la ausencia ES el cero. Decide la unidad de análisis."""
    dims = ("anio", "municipio", "mes")
    crudas = consultar("infonavit", anios, estado, "000", dims)
    df = pd.DataFrame(normalizar_filas(crudas, dims))
    if df.empty:
        return df, df

    tam = (df.groupby("municipio")["acciones"].sum()
             .sort_values(ascending=False).rename("acciones_totales"))
    celdas = df.groupby("municipio").size().rename("celdas_con_dato")
    posibles = len(anios) * 12
    perfil = pd.concat([tam, celdas], axis=1)
    perfil["cobertura_mes"] = (perfil["celdas_con_dato"] / posibles).round(3)
    perfil["acciones_por_celda"] = (perfil["acciones_totales"]
                                    / perfil["celdas_con_dato"]).round(1)

    resumen = pd.DataFrame({
        "municipios": [len(perfil)],
        "cobertura_mediana": [perfil["cobertura_mes"].median()],
        "municipios_cobertura_<25%": [(perfil["cobertura_mes"] < 0.25).sum()],
        "municipios_cobertura_>75%": [(perfil["cobertura_mes"] > 0.75).sum()],
    })
    return perfil, resumen


def merida_por_modalidad(anios=ANIOS):
    """Descompone Mérida por modalidad y prueba la predicción: al filtrar a
    adquisición (Nueva + Existente), el ticket promedio debe SUBIR de forma
    sustancial frente al ticket crudo (que mezcla mejora, pasivos y suelo)."""
    dims = ("anio", "modalidad")
    crudas = consultar("infonavit", anios, YUCATAN, MERIDA, dims)
    df = pd.DataFrame(normalizar_filas(crudas, dims))
    if df.empty:
        return df, df

    df = df.dropna(subset=["acciones", "monto"])
    df["ticket"] = df["monto"] / df["acciones"]

    ADQ = {"Nueva", "Existente"}
    crudo = (df.groupby("anio")[["acciones", "monto"]].sum()
               .assign(ticket_crudo=lambda d: d["monto"] / d["acciones"]))
    adq = (df[df["modalidad"].isin(ADQ)].groupby("anio")[["acciones", "monto"]].sum()
             .assign(ticket_adquisicion=lambda d: d["monto"] / d["acciones"]))
    comp = crudo[["ticket_crudo"]].join(adq[["ticket_adquisicion"]])
    comp["delta_%"] = ((comp["ticket_adquisicion"] / comp["ticket_crudo"] - 1)
                       * 100).round(1)
    return df, comp.round(0)


def _p(titulo, df):
    print("\n" + "=" * 78 + f"\n{titulo}\n" + "-" * 78)
    if df is None or len(df) == 0:
        print("  (sin datos)")
    else:
        with pd.option_context("display.max_columns", None, "display.width", 160):
            print(df.to_string())


def main():
    print("VALIDACIÓN v2 — INFONAVIT · método: comparación de llaves crudas\n")

    print("1/4 · Descubrimiento de dimensiones (llave real, no conteo de filas)")
    df_dims = descubrir_dimensiones(DIMS_REALES + DIMS_SOSPECHOSAS)
    _p("1/4 · Dimensiones: ¿existen y bajo qué nombre?", df_dims)

    _p("2/4 · Tope de dimensiones (solo dimensiones reales)", probar_tope())

    perfil, resumen = dispersion_mensual()
    _p("3/4 · Dispersión municipio-mes — resumen", resumen)
    _p("3/4 · Dispersión — 10 municipios más grandes", perfil.head(10))
    _p("3/4 · Dispersión — 10 más chicos", perfil.tail(10))

    detalle, comp = merida_por_modalidad()
    _p("4/4 · Mérida: ticket crudo vs ticket de adquisición", comp)
    if len(detalle):
        _p("4/4 · Mérida: acciones por modalidad (todos los años)",
           detalle.groupby("modalidad")[["acciones", "monto"]].sum()
                  .assign(ticket=lambda d: (d["monto"] / d["acciones"]).round(0))
                  .sort_values("acciones", ascending=False))


if __name__ == "__main__":
    main()

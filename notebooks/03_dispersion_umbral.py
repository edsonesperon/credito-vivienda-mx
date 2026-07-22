"""
Fase 2 · Dispersión nacional y derivación del umbral de municipios.

Lee el panel crudo (02), filtra a adquisición (modalidad ∈ {Nueva, Existente}),
mide la dispersión mensual por municipio a nivel NACIONAL, y explora umbrales de
volumen para decidir cuáles municipios son modelables.

El umbral NO se fija a ojo: sale de la distribución real. Para cada umbral
candidato se reporta cuántos municipios pasan Y qué porcentaje del volumen
nacional de adquisición cubren. El corte se elige por su cobertura del volumen,
no por un número arbitrario. Un municipio bajo umbral NO se borra: se marca
`elegible=False` y queda para un eventual respaldo anual.

Entrada: data/raw/panel_infonavit_nacional.csv
Salidas: data/processed/dispersion_municipios.csv
         data/processed/panel_adquisicion_mensual.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import pandas as pd  # noqa: E402

CRUDO = RAIZ / "data" / "raw" / "panel_infonavit_nacional.csv"
PROC = RAIZ / "data" / "processed"
ADQUISICION = {"Nueva", "Existente"}
UMBRALES = [1, 2, 3, 5, 10, 20]  # mediana de acciones de adquisición por mes
UMBRAL_ELEGIDO = 5               # cerrado en D7: mediana de acciones/mes
UMBRAL_COBERTURA = 0.5           # fracción mínima de meses con dato

# Por qué DOS criterios y no solo la mediana: la mediana se calcula sobre las
# celdas CON dato, así que un municipio con 9 meses de actividad en 8 años tiene
# mediana alta y pasaría el filtro, mientras que uno con 130 meses de actividad
# baja no. El criterio de mediana solo PREMIA LA ESCASEZ. El piso de cobertura lo
# corrige: exige que la serie exista de verdad, no solo que sus pocos puntos sean
# grandes. Caso que lo destapó: Valle de Guadalupe (Jalisco), 9 meses con dato en
# el panel, mediana 14, cobertura 0.066.


def cargar() -> pd.DataFrame:
    if not CRUDO.exists():
        raise SystemExit(f"No existe {CRUDO}. Corre primero 02_ingesta_nacional.py.")
    return pd.read_csv(CRUDO, encoding="utf-8")


def panel_adquisicion(df: pd.DataFrame):
    """Filtra a adquisición y agrega a municipio × (anio, mes). Suma sobre
    valor_vivienda (la composición por segmento se retoma en el modelado)."""
    adq = df[df["modalidad"].isin(ADQUISICION)].copy()
    llave = "clave_municipio" if "clave_municipio" in adq.columns else "municipio"
    claves = ["estado", llave, "municipio", "anio", "mes_num"]
    panel = (adq.groupby(claves, dropna=False)[["acciones", "monto"]]
                .sum().reset_index())
    return panel, llave


def dispersion(panel: pd.DataFrame, llave: str):
    """Perfil por municipio: cobertura mensual, volumen total y mediana mensual.
    `meses_posibles` = número de (anio, mes) distintos que existen en TODO el
    panel nacional; es la longitud real de la serie, no una suposición."""
    meses_posibles = panel[["anio", "mes_num"]].drop_duplicates().shape[0]
    disp = (panel.groupby(["estado", llave, "municipio"], dropna=False)
                 .agg(celdas_con_dato=("acciones", "size"),
                      acciones_totales=("acciones", "sum"),
                      mediana_mensual=("acciones", "median"),
                      monto_total=("monto", "sum"))
                 .reset_index())
    disp["cobertura"] = (disp["celdas_con_dato"] / meses_posibles).round(3)
    disp = disp.sort_values("acciones_totales", ascending=False).reset_index(drop=True)
    return disp, meses_posibles


def barrido_umbral(disp: pd.DataFrame) -> pd.DataFrame:
    """Para cada umbral candidato: municipios que pasan y % del volumen nacional
    de adquisición que cubren. Es la tabla que permite elegir el corte con
    criterio de cobertura, no a ojo."""
    total_acc = disp["acciones_totales"].sum()
    total_monto = disp["monto_total"].sum()
    filas = []
    for u in UMBRALES:
        elig = disp[(disp["mediana_mensual"] >= u) & (disp["cobertura"] >= UMBRAL_COBERTURA)]
        filas.append({
            "umbral_mediana_mensual": u,
            "municipios_elegibles": len(elig),
            "pct_municipios": round(100 * len(elig) / max(len(disp), 1), 1),
            "pct_acciones_cubiertas": round(100 * elig["acciones_totales"].sum() / total_acc, 1),
            "pct_monto_cubierto": round(100 * elig["monto_total"].sum() / total_monto, 1),
        })
    return pd.DataFrame(filas)


def _p(titulo, df, n=None):
    print("\n" + "=" * 80 + f"\n{titulo}\n" + "-" * 80)
    x = df if n is None else df.head(n)
    with pd.option_context("display.max_columns", None, "display.width", 170):
        print(x.to_string(index=False))


def main():
    df = cargar()
    print(f"Panel crudo: {len(df)} filas, columnas {list(df.columns)}")

    modos = df.groupby("modalidad")["acciones"].sum().sort_values(ascending=False)
    _p("Composición por modalidad (todo el país) — qué se filtra y qué se queda",
       modos.reset_index())

    panel, llave = panel_adquisicion(df)
    disp, meses = dispersion(panel, llave)
    print(f"\nMeses posibles en el panel (longitud de serie): {meses}")
    print(f"Municipios con adquisición: {len(disp)}")

    barr = barrido_umbral(disp)
    _p("Barrido de umbral — municipios vs. cobertura del volumen nacional", barr)

    disp["elegible"] = ((disp["mediana_mensual"] >= UMBRAL_ELEGIDO)
                        & (disp["cobertura"] >= UMBRAL_COBERTURA))
    descartados_cobertura = int(((disp["mediana_mensual"] >= UMBRAL_ELEGIDO)
                                 & (disp["cobertura"] < UMBRAL_COBERTURA)).sum())
    n_elig = int(disp["elegible"].sum())
    print(f"\nCriterio: mediana >= {UMBRAL_ELEGIDO} acciones/mes Y cobertura >= {UMBRAL_COBERTURA}")
    print(f"  descartados por cobertura pese a pasar la mediana: {descartados_cobertura}")
    print(f"  elegibles: {n_elig} municipios "
          f"({round(100*n_elig/len(disp),1)}% de municipios, "
          f"{round(100*disp[disp['elegible']]['acciones_totales'].sum()/disp['acciones_totales'].sum(),1)}% del volumen).")

    _p("20 municipios más grandes (adquisición)", disp, 20)
    _p("15 municipios en la frontera del umbral",
       disp[disp["mediana_mensual"].between(UMBRAL_ELEGIDO - 1, UMBRAL_ELEGIDO + 2)], 15)

    PROC.mkdir(parents=True, exist_ok=True)
    disp.to_csv(PROC / "dispersion_municipios.csv", index=False, encoding="utf-8")
    panel.to_csv(PROC / "panel_adquisicion_mensual.csv", index=False, encoding="utf-8")
    print(f"\nGuardado en {PROC.name}/: dispersion_municipios.csv, panel_adquisicion_mensual.csv")


if __name__ == "__main__":
    main()

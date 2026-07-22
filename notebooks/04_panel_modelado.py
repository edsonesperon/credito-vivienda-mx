"""
Fase 3 · Construcción del panel de modelado, con detección de quiebres.

Toma el panel de adquisición (03), lo restringe a los municipios elegibles y lo
convierte en un panel balanceado, rellenando con CERO los meses sin crédito.

REGLA DE RELLENADO (corregida tras el caso Villa de Pozos):
    Se rellena con cero SOLO desde el primer mes observado de cada municipio en
    adelante. ANTES de esa primera observación NO se rellena: queda fuera del
    panel. Motivo: un municipio puede no haber existido. Villa de Pozos (SLP,
    clave 59) fue creado el 23 de julio de 2024 por secesión del municipio de
    San Luis Potosí; sus "ceros" de 2015-2024 no son ausencia de crédito, son
    ausencia de municipio. Rellenarlos afirma un hecho falso, fabrica 118 meses
    de historia inexistente y contamina cualquier evaluación posterior.
    Después de la primera observación, un mes ausente SÍ es cero real.

El panel resultante es DESBALANCEADO a propósito: cada municipio empieza cuando
empieza. Los que no alcanzan historia mínima para pronosticar quedan marcados,
no borrados.

DETECCIÓN DE QUIEBRES: se reportan municipios con arranque tardío (posible
creación), corte al final (posible desaparición o fusión) y cambios de nivel
abruptos (posible pérdida/ganancia de territorio, como el municipio padre de una
secesión). Son candidatos a exclusión o a tratamiento especial en el modelado.

Entrada: data/processed/dispersion_municipios.csv
         data/processed/panel_adquisicion_mensual.csv
Salidas: data/interim/panel_modelado.csv
         data/processed/quiebres_detectados.csv
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

PROC = RAIZ / "data" / "processed"
INTERIM = RAIZ / "data" / "interim"
DISP = PROC / "dispersion_municipios.csv"
PANEL = PROC / "panel_adquisicion_mensual.csv"
SALIDA = INTERIM / "panel_modelado.csv"
QUIEBRES = PROC / "quiebres_detectados.csv"

LLAVE = ["estado", "clave_municipio"]
HIST_MINIMA = 36        # 2 estaciones (24) + horizonte de prueba (12)
MESES_ARRANQUE_TARDIO = 12   # arrancar >12 meses después del panel es sospechoso
MESES_CORTE_FINAL = 6        # dejar de reportar >6 meses antes del fin es sospechoso


def cargar():
    if not (DISP.exists() and PANEL.exists()):
        raise SystemExit("Faltan los CSV de processed/. Corre antes 03_dispersion_umbral.py.")
    return pd.read_csv(DISP), pd.read_csv(PANEL)


def _fecha(anio, mes):
    return pd.to_datetime(f"{int(anio)}-{int(mes):02d}-01")


def construir(disp: pd.DataFrame, panel: pd.DataFrame):
    elig = disp[disp["elegible"]][LLAVE + ["municipio"]].drop_duplicates()
    reales = panel.merge(elig[LLAVE], on=LLAVE, how="inner")
    reales = (reales.groupby(LLAVE + ["anio", "mes_num"], dropna=False)
                    [["acciones", "monto"]].sum().reset_index())
    reales["fecha"] = [_fecha(a, m) for a, m in zip(reales["anio"], reales["mes_num"])]

    fecha_fin = reales["fecha"].max()
    piezas = []
    for llave, g in reales.groupby(LLAVE):
        inicio = g["fecha"].min()
        rejilla = pd.date_range(inicio, fecha_fin, freq="MS")   # desde SU inicio
        base = pd.DataFrame({"fecha": rejilla})
        base["estado"], base["clave_municipio"] = llave
        m = base.merge(g[["fecha", "acciones", "monto"]], on="fecha", how="left")
        m["acciones"] = m["acciones"].fillna(0.0)   # cero real: ya existía
        m["monto"] = m["monto"].fillna(0.0)
        piezas.append(m)

    df = pd.concat(piezas, ignore_index=True)
    df = df.merge(elig, on=LLAVE, how="left")
    df["anio"] = df["fecha"].dt.year
    df["mes_num"] = df["fecha"].dt.month
    df["ticket"] = np.where(df["acciones"] > 0, df["monto"] / df["acciones"].replace(0, np.nan), np.nan)
    return df.sort_values(LLAVE + ["fecha"]).reset_index(drop=True), reales, fecha_fin


def detectar_quiebres(reales: pd.DataFrame, fecha_fin) -> pd.DataFrame:
    """Marca series con arranque tardío, corte final o cambio de nivel abrupto."""
    fecha_ini_panel = reales["fecha"].min()
    filas = []
    for llave, g in reales.groupby(LLAVE):
        g = g.sort_values("fecha")
        ini, fin = g["fecha"].min(), g["fecha"].max()
        meses_tarde = (ini.year - fecha_ini_panel.year) * 12 + (ini.month - fecha_ini_panel.month)
        meses_corte = (fecha_fin.year - fin.year) * 12 + (fecha_fin.month - fin.month)
        n = len(g)
        acc = g["acciones"].to_numpy(dtype=float)
        # cambio de nivel: media de la 2a mitad contra la 1a (evita división por 0)
        if n >= 24:
            h = n // 2
            m1, m2 = acc[:h].mean(), acc[h:].mean()
            razon = float(m2 / m1) if m1 > 0 else np.inf
        else:
            razon = np.nan

        motivos = []
        if meses_tarde > MESES_ARRANQUE_TARDIO:
            motivos.append("arranque_tardio")
        if meses_corte > MESES_CORTE_FINAL:
            motivos.append("corte_final")
        if pd.notna(razon) and (razon > 3 or razon < 1 / 3):
            motivos.append("cambio_de_nivel")
        if n < HIST_MINIMA:
            motivos.append("historia_insuficiente")

        if motivos:
            filas.append({"estado": llave[0], "clave_municipio": llave[1],
                          "meses_observados": n, "primer_mes": ini.strftime("%Y-%m"),
                          "ultimo_mes": fin.strftime("%Y-%m"),
                          "meses_arranque_tardio": meses_tarde,
                          "meses_corte_final": meses_corte,
                          "razon_nivel_2a_1a_mitad": round(razon, 2) if pd.notna(razon) else None,
                          "motivos": "|".join(motivos)})
    return pd.DataFrame(filas)


def main():
    disp, panel = cargar()
    df, reales, fecha_fin = construir(disp, panel)
    nombres = disp[LLAVE + ["municipio"]].drop_duplicates()

    n_mun = df.groupby(LLAVE).ngroups
    hist = df.groupby(LLAVE).size().rename("meses")
    suficientes = int((hist >= HIST_MINIMA).sum())

    print("PANEL DE MODELADO")
    print(f"  municipios elegibles      : {n_mun}")
    print(f"  rango del panel           : {df['fecha'].min():%Y-%m} a {df['fecha'].max():%Y-%m}")
    print(f"  filas                     : {len(df)}")
    print(f"  con historia >= {HIST_MINIMA} meses : {suficientes}  "
          f"(los demás no son pronosticables aún)")
    print(f"  meses en cero             : {round(100*(df['acciones']==0).mean(),1)}%  (ceros reales)")
    print(f"  acciones totales          : {int(df['acciones'].sum())}")

    q = detectar_quiebres(reales, fecha_fin)
    print("\n" + "=" * 78)
    print("QUIEBRES DETECTADOS — series que NO son un histórico limpio")
    print("-" * 78)
    if len(q):
        q = q.merge(nombres, on=LLAVE, how="left")
        cols = ["estado", "clave_municipio", "municipio", "meses_observados",
                "primer_mes", "ultimo_mes", "razon_nivel_2a_1a_mitad", "motivos"]
        print(q.sort_values("meses_observados")[cols].to_string(index=False))
        print(f"\n  {len(q)} municipios con al menos un quiebre. Revisar antes de modelar.")
    else:
        print("  ninguno")

    mer = df[(df["estado"] == 31) & (df["clave_municipio"] == 50)]
    if len(mer):
        print(f"\n  Sanidad — Mérida: {len(mer)} meses, "
              f"{mer['fecha'].min():%Y-%m} a {mer['fecha'].max():%Y-%m}, "
              f"{int(mer['acciones'].sum())} acciones")

    INTERIM.mkdir(parents=True, exist_ok=True)
    df.to_csv(SALIDA, index=False, encoding="utf-8")
    q.to_csv(QUIEBRES, index=False, encoding="utf-8")
    print(f"\nGuardado: {SALIDA.relative_to(RAIZ)}, {QUIEBRES.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()

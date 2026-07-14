"""
Pruebas de la capa de normalización contra respuestas REALES observadas en los
ejemplos oficiales de datos abiertos del SNIIV. Sin red: son fixtures tomadas
literalmente de la documentación (endpoints GetINFONAVIT / GetCNBV / GetCONAVI)
y de la validación empírica de la fuente (el mes como nombre en español).

Lo que estas pruebas SÍ verifican: que el parser sobrevive a las inconsistencias
reales de la API (año/anio, sexo/genero, número vs cadena, acciones vacía, llave
faltante, mes como nombre). Lo que NO pueden verificar: la ruta de red contra la
API viva. Esa parte se valida con notebooks/01_validacion_v2.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ingesta_sniiv import _a_numero, _a_mes, normalizar_filas  # noqa: E402

# --- Fixtures: filas tal como aparecen en los ejemplos oficiales del SNIIV ----

# GetINFONAVIT/2018/08/005/anio,municipio,genero
# Nota: la 1a fila NO trae la llave del año (inconsistencia real observada).
INFONAVIT_2018 = [
    {"municipio": "Ascensión", "sexo": "Hombre", "acciones": 13, "monto": 3973467.36},
    {"año": 2018, "municipio": "Ascensión", "sexo": "Mujer", "acciones": 9, "monto": 1527404.93},
]

# GetCNBV/2018/08/005/anio,municipio,genero
CNBV_2018 = [
    {"año": 2018, "municipio": "Ascensión", "sexo": "Hombre", "acciones": 3, "monto": 749866},
    {"año": 2018, "municipio": "Ascensión", "sexo": "Mujer", "acciones": 3, "monto": 65406},
]

# GetCONAVI/... : monto como cadena y acciones vacía (inconsistencias reales)
CONAVI_MIX = [
    {"año": "2018", "municipio": "Calpan", "modalidad": "Mejoramiento", "acciones": "", "monto": "1087800"},
    {"año": "2019", "municipio": "Calpan", "modalidad": "Reconstrucción", "acciones": "37", "monto": "5515000"},
]


def test_coercion_numerica():
    assert _a_numero(13) == 13
    assert _a_numero("37") == 37
    assert _a_numero("5515000") == 5515000
    assert _a_numero(3973467.36) == 3973467.36
    assert _a_numero("") is None          # acciones vacía -> None, no 0 inventado
    assert _a_numero(None) is None
    assert _a_numero("1,201,286") == 1201286  # por si viniera con separador de miles


def test_alias_anio_y_genero():
    norm = normalizar_filas(INFONAVIT_2018, ("anio", "municipio", "genero"))
    # 'sexo' -> 'genero'; 'año' -> 'anio'
    assert all("genero" in f and "sexo" not in f for f in norm)
    assert all("anio" in f for f in norm)
    assert norm[1]["anio"] == 2018
    # La 1a fila no traía año: debe quedar None y ser VISIBLE, no disimulado.
    assert norm[0]["anio"] is None


def test_medidas_preservan_valor_real():
    norm = normalizar_filas(INFONAVIT_2018, ("anio", "municipio", "genero"))
    # El monto de INFONAVIT trae pesos reales (refuta el "monto=0" de antes).
    assert norm[0]["monto"] == 3973467.36
    assert norm[0]["acciones"] == 13


def test_conavi_cadena_y_vacia():
    norm = normalizar_filas(CONAVI_MIX, ("anio", "municipio", "modalidad"))
    assert norm[0]["acciones"] is None       # "" -> None
    assert norm[0]["monto"] == 1087800       # "1087800" -> 1087800
    assert norm[1]["acciones"] == 37
    assert norm[0]["anio"] == 2018           # "2018" (cadena) -> 2018 (entero)


def test_dimension_faltante_se_hace_visible():
    # Si se pide una dimensión que la respuesta no trajo, aparece como None.
    norm = normalizar_filas(CNBV_2018, ("anio", "municipio", "genero", "segmento"))
    assert all(f["segmento"] is None for f in norm)


def test_mes_nombre_a_numero():
    # La API devuelve el mes como NOMBRE en español, no como número (observado).
    assert _a_mes("abril") == 4
    assert _a_mes("Enero") == 1        # la API puede capitalizar
    assert _a_mes("diciembre") == 12
    assert _a_mes(7) == 7
    assert _a_mes("bruma") is None     # desconocido -> None, no se inventa

    filas = [{"año": 2026, "municipio": "Mérida", "mes": "abril",
              "acciones": 500, "monto": 300000000}]
    norm = normalizar_filas(filas, ("anio", "municipio", "mes"))
    assert norm[0]["mes"] == "abril"   # el nombre original se conserva
    assert norm[0]["mes_num"] == 4     # y se agrega el número


if __name__ == "__main__":
    import traceback

    pruebas = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fallos = 0
    for prueba in pruebas:
        try:
            prueba()
            print(f"PASS  {prueba.__name__}")
        except AssertionError:
            fallos += 1
            print(f"FAIL  {prueba.__name__}")
            traceback.print_exc()
    print(f"\n{len(pruebas) - fallos}/{len(pruebas)} pruebas en verde")
    sys.exit(1 if fallos else 0)

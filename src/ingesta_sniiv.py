"""
Cliente de ingesta para la CuboAPI del SNIIV (SEDATU).

Principio de diseño (no negociable en este proyecto):
    Este módulo NO asume ningún valor que no haya sido observado en una respuesta
    real de la API. En particular NO asume:
      - hasta qué año hay datos cargados,
      - qué dimensiones acepta cada organismo (p. ej. `mes`, `segmento`),
      - la existencia de un comodín de "todos los estados".
    Eso se DESCUBRE con notebooks/00_validacion_fuente.py contra la API viva.
    Aquí solo vive la mecánica de consulta y de normalización, probada contra las
    respuestas de ejemplo documentadas (ver tests/test_ingesta_sniiv.py).

Diseño agnóstico a la fuente:
    Un único constructor de URL sirve a todos los organismos vía el registro
    ORGANISMOS. Agregar CNBV (fuente #2) es una entrada en ese diccionario y una
    nueva corrida; no se reescribe la mecánica.

Gramática confirmada de la URL (ejemplos oficiales de datos abiertos del SNIIV):
    GET {BASE}/Get{Organismo}/{años}/{estado}/{municipio}/{dimensiones}
      años        -> "2018", o "2020,2021" (lista o rango)
      estado      -> clave INEGI de 2 dígitos ("08", "31", ...)
      municipio   -> clave INEGI de 3 dígitos, o "000" para todos los del estado
      dimensiones -> lista separada por comas (máx. observado en ejemplos: 5)
    Medidas devueltas SIEMPRE: `acciones` y `monto`.

Observado para INFONAVIT (ejemplo oficial, estado 08 / municipio 005):
    GET .../GetINFONAVIT/2018/08/005/anio,municipio,genero
    -> [{"municipio": "...", "sexo": "...", "acciones": 13, "monto": 3973467.36}, ...]
    Notas de la inconsistencia real de la API, que la normalización maneja:
      - se pide `genero` en la dimensión pero la respuesta trae `sexo`;
      - se pide `anio` pero la respuesta a veces trae `año`;
      - `acciones`/`monto` pueden venir como número o como cadena, y `acciones`
        puede venir vacía ("").
"""

from __future__ import annotations

import json
import time
from typing import Any, Iterable, Sequence

import requests

BASE_URL = "https://sniiv.sedatu.gob.mx/api/CuboAPI"

# Registro agnóstico a la fuente. Clave corta -> segmento de ruta del endpoint.
# Confirmados por ejemplos oficiales. Agregar una fuente = agregar un renglón.
ORGANISMOS: dict[str, str] = {
    "infonavit": "GetINFONAVIT",
    "fovissste": "GetFOVISSSTE",
    "cnbv": "GetCNBV",
    "conavi": "GetCONAVI",
    "insus": "GetInsus",
    "fonhapo": "GetFONHAPO",
    "financiamiento": "GetFinanciamiento",  # agregado; no usar como target
}

# 32 entidades federativas (clave INEGI de 2 dígitos). Se itera explícitamente
# en lugar de asumir un comodín de "todos los estados" que no se ha observado.
ESTADOS: tuple[str, ...] = tuple(f"{i:02d}" for i in range(1, 33))

# Alias de campo OBSERVADOS en respuestas reales (no inventados). La respuesta
# se normaliza a las llaves de la izquierda -> derecha.
ALIAS_CAMPOS: dict[str, str] = {
    "año": "anio",
    "sexo": "genero",
}

MEDIDAS: tuple[str, ...] = ("acciones", "monto")

# Dimensiones-llave temporales: la API las devuelve como entero en unos
# organismos y como cadena en otros (p. ej. `año` es 2018 en INFONAVIT y "2018"
# en CONAVI). Se unifican a entero para que las agrupaciones por periodo no se
# rompan en silencio. No se toca el tipo de las demás dimensiones.
DIMS_ENTERAS: tuple[str, ...] = ("anio", "mes")


class ErrorConsultaSNIIV(RuntimeError):
    """La API no devolvió una respuesta utilizable para la consulta dada."""


def construir_url(
    organismo: str,
    anios: str | int | Sequence[int | str],
    estado: str,
    municipio: str,
    dimensiones: Sequence[str],
) -> str:
    """Arma la URL de consulta según la gramática confirmada.

    No valida qué dimensiones son legales para el organismo: eso lo resuelve la
    validación empírica, no una suposición de este módulo.
    """
    if organismo not in ORGANISMOS:
        raise KeyError(
            f"organismo desconocido: {organismo!r}. Conocidos: {sorted(ORGANISMOS)}"
        )
    if isinstance(anios, (list, tuple)):
        anios_txt = ",".join(str(a) for a in anios)
    else:
        anios_txt = str(anios)
    dims_txt = ",".join(dimensiones)
    endpoint = ORGANISMOS[organismo]
    return f"{BASE_URL}/{endpoint}/{anios_txt}/{estado}/{municipio}/{dims_txt}"


def consultar(
    organismo: str,
    anios: str | int | Sequence[int | str],
    estado: str,
    municipio: str = "000",
    dimensiones: Sequence[str] = ("anio", "municipio"),
    *,
    timeout: float = 30.0,
    reintentos: int = 3,
    pausa_base: float = 1.5,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    """Consulta un cubo y devuelve la lista de filas CRUDAS (sin normalizar).

    La respuesta viene como text/plain con cuerpo JSON. Se intenta parsear como
    JSON; si falla, se levanta ErrorConsultaSNIIV con el texto para diagnóstico.
    Reintenta ante errores de red/5xx con backoff; no reintenta ante 4xx (una
    dimensión ilegal es información, no un fallo transitorio).
    """
    url = construir_url(organismo, anios, estado, municipio, dimensiones)
    sess = session or requests.Session()
    ultimo_error: Exception | None = None

    for intento in range(1, reintentos + 1):
        try:
            resp = sess.get(url, headers={"accept": "text/plain"}, timeout=timeout)
        except requests.RequestException as exc:  # red: sí reintenta
            ultimo_error = exc
            time.sleep(pausa_base * intento)
            continue

        if resp.status_code >= 500:  # servidor: sí reintenta
            ultimo_error = ErrorConsultaSNIIV(
                f"HTTP {resp.status_code} en {url}"
            )
            time.sleep(pausa_base * intento)
            continue
        if resp.status_code >= 400:  # cliente: NO reintenta, informa
            raise ErrorConsultaSNIIV(
                f"HTTP {resp.status_code} en {url} :: {resp.text[:300]}"
            )

        texto = resp.text.strip()
        if not texto:
            return []
        try:
            datos = json.loads(texto)
        except json.JSONDecodeError as exc:
            raise ErrorConsultaSNIIV(
                f"respuesta no-JSON en {url} :: {texto[:300]}"
            ) from exc

        if isinstance(datos, dict):
            datos = [datos]
        if not isinstance(datos, list):
            raise ErrorConsultaSNIIV(f"forma inesperada en {url}: {type(datos)}")
        return datos

    raise ErrorConsultaSNIIV(f"agotados los reintentos en {url}") from ultimo_error


def _a_numero(valor: Any) -> float | int | None:
    """Coerciona a número. Cadena vacía o None -> None. No inventa ceros."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return valor
    txt = str(valor).strip().replace(",", "")
    if txt == "":
        return None
    try:
        num = float(txt)
    except ValueError:
        return None
    return int(num) if num.is_integer() else num


def normalizar_filas(
    filas: Iterable[dict[str, Any]],
    dimensiones_solicitadas: Sequence[str],
) -> list[dict[str, Any]]:
    """Normaliza filas crudas: aplica alias observados, coerciona medidas y
    garantiza que cada dimensión solicitada exista (con None si faltó en la
    respuesta, para que un faltante sea visible y no se disimule).
    """
    dims_norm = [ALIAS_CAMPOS.get(d, d) for d in dimensiones_solicitadas]
    salida: list[dict[str, Any]] = []
    for fila in filas:
        fila_norm: dict[str, Any] = {}
        for k, v in fila.items():
            fila_norm[ALIAS_CAMPOS.get(k, k)] = v
        for medida in MEDIDAS:
            if medida in fila_norm:
                fila_norm[medida] = _a_numero(fila_norm[medida])
        for dim in DIMS_ENTERAS:
            if fila_norm.get(dim) is not None:
                num = _a_numero(fila_norm[dim])
                # solo unifica si es un entero limpio; si no, deja el valor
                # original visible en vez de disimularlo con None.
                fila_norm[dim] = int(num) if isinstance(num, int) else fila_norm[dim]
        for dim in dims_norm:
            fila_norm.setdefault(dim, None)
        salida.append(fila_norm)
    return salida


def extraer_panel_nacional(
    organismo: str,
    anios: str | int | Sequence[int | str],
    dimensiones: Sequence[str],
    *,
    estados: Sequence[str] = ESTADOS,
    municipio: str = "000",
    pausa: float = 0.5,
    session: requests.Session | None = None,
    on_error: str = "continuar",  # "continuar" | "abortar"
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Itera las entidades y arma el panel nacional (municipio="000" = todos).

    NO fija las dimensiones: se pasan explícitamente porque cuáles son legales lo
    decide la validación empírica, no este módulo. Devuelve (filas, incidencias);
    cada fila lleva su `estado_consultado` de procedencia.
    """
    sess = session or requests.Session()
    filas: list[dict[str, Any]] = []
    incidencias: list[dict[str, Any]] = []
    for est in estados:
        try:
            crudas = consultar(
                organismo, anios, est, municipio, dimensiones, session=sess
            )
        except ErrorConsultaSNIIV as exc:
            incidencias.append({"estado": est, "error": str(exc)})
            if on_error == "abortar":
                raise
            continue
        for f in normalizar_filas(crudas, dimensiones):
            f["estado_consultado"] = est
            filas.append(f)
        time.sleep(pausa)  # cortesía con el servidor
    return filas, incidencias

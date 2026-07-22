# Observatorio de Vivienda Financiada

Sistema de *machine learning* de punta a punta que estima la demanda de crédito
de vivienda a nivel municipal en México, con foco de despliegue en Mérida y el
sureste. Tercer proyecto de una línea sobre vivienda del sureste, y salto
deliberado hacia **ML engineering / MLOps**: no solo modelar, sino ingerir,
versionar, servir, monitorear y reentrenar un modelo vivo.

> **Estado:** en construcción — Fase 4 (modelo). Fases 0-3 completas: andamiaje,
> validación de la fuente, ingesta nacional con análisis de dispersión, y panel de
> modelado con su piso de baselines. Ver `docs/decisiones.md` para el detalle de lo
> decidido y las trampas del dato documentadas.

## Qué hace

- **Medida objetivo:** monto de crédito de adquisición (`modalidad ∈ {Nueva,
  Existente}`), modelado en dos componentes — número de acciones × ticket
  promedio — por municipio y mes, con desglose por segmento.
- **Universo de modelado:** panel mensual 2015-2026 sobre los 316 municipios que
  superan un criterio doble (mediana ≥ 5 acciones de adquisición/mes Y cobertura
  ≥ 50% de los meses), derivado de la distribución nacional, no fijado a ojo.
  Cubren 97.7% del volumen; los demás se marcan, no se borran.
- **Enfoque de entrenamiento:** panel nacional (los municipios de pocos datos
  toman fuerza prestada de los de muchos); despliegue con foco en Mérida y el
  sureste. La especialización local vive en el dominio y el producto, no en
  recortar el set de entrenamiento.
- **Criterio de éxito:** primario — superar el piso de baselines fuera de muestra
  (MASE mediano 0.760 y medio 0.847 sobre acciones, ETS estacional), con
  validación temporal; secundario — diagnóstico de transferibilidad (modelo
  nacional vs. solo-Mérida).

Un hallazgo que orientó el diseño: entre 2015 y 2025 el número de créditos de
adquisición cayó 7% mientras el monto creció 2.35x. El mercado no crece en
volumen, se encarece. Por eso el target pronosticable es el conteo de acciones, y
el precio se modela por separado.

## Estructura

```
credito-vivienda-mx/
├── data/{raw,interim,processed}/   dato crudo → intermedio → panel final (no versionado)
├── docs/                           visión, fuentes, decisiones (bitácora)
├── notebooks/                      exploración numerada (00_, 01_, …)
├── src/                            código reutilizable e importable
├── tests/                          pruebas del código de src/
└── outputs/                        entregables (reportes, exportes)
```

## Instalación

```bash
conda env create -f environment.yml
conda activate credito-vivienda-mx
```

## Uso

```bash
# Sanidad del parser, sin red (6/6 en verde)
python tests/test_ingesta_sniiv.py

# Validación de la fuente contra la API viva del SNIIV
python notebooks/00_validacion_fuente.py
python notebooks/01_validacion_v2.py

# Ingesta nacional y análisis de dispersión (define el universo de modelado)
python notebooks/02_ingesta_nacional.py     # lento: toca la red
python notebooks/03_dispersion_umbral.py    # local: filtra, mide, deriva el umbral

# Panel de modelado y piso de baselines
python notebooks/04_panel_modelado.py       # panel balanceado + detección de quiebres
python notebooks/05_baselines.py            # seasonal-naive y ETS, evaluación temporal
```

La validación **descubre** —no asume— qué años tiene la API, qué dimensiones
acepta y su comportamiento real. Todo se deriva de la respuesta.

## Hoja de ruta (fases)

0. **Andamiaje del repo** — entorno, estructura, convenciones. (completada)
1. **Validación de la fuente** — arnés empírico; resuelve las incógnitas de la API. (completada)
2. **Ingesta nacional + dispersión** — panel crudo nacional; umbral de municipios. (completada)
3. **Panel de modelado y baselines** — panel limpio; baselines seasonal-naive y ETS. (completada)
4. **Modelo** — evaluación temporal contra el piso, tracking (MLflow). (en proceso)
5. Servicio (API) + contenedor (Docker).
6. Monitoreo, reentrenamiento programado, CI.
7. Tablero e indicadores de producto (incluida la brecha de asequibilidad como salida).

## Fuentes

- **SNIIV — CuboAPI** (SEDATU/Conavi): columna vertebral de la demanda financiada.
- **Índice SHF de Precios de la Vivienda**: ancla de precio para asequibilidad.
- **INEGI**: features municipales.

Detalle, procedencia y trampas de cada fuente en `docs/fuentes-y-procedencia.md`.

## Convenciones

- Progresión secuencial, una decisión a la vez, con justificación explícita.
- Código reutilizable en `src/`, exploración en `notebooks/`.
- **Commits:** Conventional Commits — tipo en inglés (`feat`/`fix`/`docs`/`chore`/
  `test`/`refactor`) + descripción en español, imperativa, minúscula, ≤50
  caracteres, sin punto, sin ámbitos.
- Rigor: citar fuentes, no inventar, marcar el nivel de confianza del dato,
  documentar las trampas.

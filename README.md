# Observatorio de Vivienda Financiada

Sistema de *machine learning* de punta a punta que estima la demanda de crédito
de vivienda a nivel municipal en México, con foco de despliegue en Mérida y el
sureste. Tercer proyecto de una línea sobre vivienda del sureste, y salto
deliberado hacia **ML engineering / MLOps**: no solo modelar, sino ingerir,
versionar, servir, monitorear y reentrenar un modelo vivo.

> **Estado:** en construcción — Fase 1 (validación de la fuente). El pull
> nacional, el panel y el modelo se construyen **sobre los resultados** de esa
> validación, no antes. Ver `docs/decisiones.md` para el detalle de lo decidido
> y lo pendiente.

## Qué hace

- **Medida objetivo:** monto de crédito de adquisición, modelado en dos
  componentes — número de acciones × ticket promedio — por municipio y periodo,
  con desglose por segmento.
- **Enfoque de entrenamiento:** panel nacional de municipios (los municipios de
  pocos datos toman fuerza prestada de los de muchos); despliegue con foco en
  Mérida y el sureste. La especialización local vive en el dominio y el producto,
  no en recortar el set de entrenamiento.
- **Criterio de éxito:** el modelo debe superar a un baseline *seasonal-naive* y
  a un ETS fuera de muestra, con validación temporal. Si no, el entregable es el
  pipeline, y se le llama por su nombre.

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
# 1) Sanidad del parser, sin red (debe dar 5/5 en verde)
python tests/test_ingesta_sniiv.py

# 2) Validación de la fuente contra la API viva del SNIIV
#    (requiere alcanzar sniiv.sedatu.gob.mx)
python notebooks/00_validacion_fuente.py
```

La validación **descubre** —no asume— qué años tiene la API, qué dimensiones
acepta (incluido si existe `mes`), su tope de dimensiones y la dispersión de
Mérida. Todo se deriva de la respuesta real.

## Hoja de ruta (fases)

0. **Andamiaje del repo** — entorno, estructura, convenciones. ✅
1. **Validación de la fuente** — arnés empírico; resuelve la bitácora de
   decisiones abiertas. ⏳
2. Ingesta nacional reproducible + modelo de datos (panel municipio-periodo-segmento).
3. EDA del panel y baselines.
4. Modelo, evaluación temporal contra baselines, tracking (MLflow).
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

# Observatorio de Vivienda Financiada — visión del proyecto

**Repositorio propuesto:** `credito-vivienda-mx`
(alternativas a decidir: `demanda-vivienda-mx`, `observatorio-credito-vivienda`)

**Estado:** documento vivo. Recoge únicamente lo ya decidido en la etapa de
definición. Las cuestiones sin resolver están al final, en la bitácora de
decisiones abiertas, y no deben leerse como cerradas.

---

## 1. Contexto y continuidad

Tercer proyecto de la línea de vivienda del sureste, y salto deliberado en
complejidad hacia **Machine Learning Engineering** (incluyendo su subconjunto
operativo, MLOps). Los dos previos cubrieron piezas que este integra y supera:

- `dataset-inmuebles-merida` — lado de la oferta; modelado (Gradient Boosting)
  y despliegue básico (FastAPI). Mostró modelo, no ciclo de producción.
- `vivienda-formal-merida` — lado de la demanda financiada; análisis
  reproducible sobre datos SNIIV/Infonavit. Mostró dato y dominio, no ingeniería
  de sistema.

Lo que ninguno evidenció, y que este proyecto existe para demostrar: ingesta
automatizada, versionado y servicio de modelo, contenedorización, monitoreo y
reentrenamiento — un modelo vivo, no un notebook.

## 2. Problema y propuesta de valor

Un desarrollador, una institución financiera o un organismo de planeación que
decide **en qué segmento y en qué municipio** colocar producto se juega un error
de varios millones de pesos si lee mal la demanda de crédito. La información
existe (SNIIV es público y programático), pero está cruda, dispersa y llena de
trampas de dominio. El valor está en convertir esa fuente en una señal
predictiva y accionable, entregada de forma confiable y recurrente.

**A quién sirve:** desarrolladores medianos (decisión de qué/dónde construir),
banca dimensionando cartera, e institutos de planeación como IMPLAN. El
entregable comercial no es el modelo crudo, sino el reporte/tablero recurrente
que ese modelo alimenta.

## 3. Objetivos

**General.** Construir y operar un sistema de ML de punta a punta que estime la
demanda de crédito de vivienda a nivel municipal y derive de ella indicadores de
mercado accionables, con foco de despliegue en Mérida y el sureste.

**Específicos.**
1. Ingesta reproducible y automatizada del panel municipal del SNIIV, con
   validación de esquema y manejo explícito de las trampas del dato.
2. Un modelo de estimación de demanda de crédito (medida objetivo en §4) que
   **le gane a un baseline ingenuo** de forma verificable y fuera de muestra.
3. Servicio del modelo (API) y un tablero desplegado con los indicadores.
4. Columna operativa: versionado de datos y modelo, tracking de experimentos,
   reentrenamiento programado y monitoreo de drift y de calidad de la fuente.
5. Documentación y commits de calidad de portafolio, con bitácora de decisiones.

## 4. Medida objetivo (decidido)

**Monto de crédito de adquisición**, modelado en dos componentes —**número de
acciones × ticket promedio**— por municipio y periodo, con desglose por segmento.

Justificación: el monto carga la señal de *desplazamiento hacia mayor valor* que
el conteo puro descarta; separarlo en acciones y ticket evita mezclar "más
créditos" con "créditos más caros", que son decisiones distintas para el usuario.

**Descartado como target de modelo:** la *brecha de asequibilidad*. No tiene
etiqueta medida contra la cual validar; es un índice construido, no una variable
observada. Se calcula como **salida del producto** a partir de insumos estimados,
no como algo que el modelo aprende.

## 5. Enfoque de entrenamiento (decidido)

**Entrenar sobre el panel nacional de municipios; desplegar con foco en Mérida y
el sureste.** Restringir el entrenamiento a un municipio no es especializar: es
inanición estadística. El panel nacional permite que los municipios de pocos
datos tomen fuerza prestada de los de muchos (partial pooling) y hace legítimo un
modelo de ML de verdad. La especialización meridana vive en la capa de dominio,
producto y despliegue — no en recortar el set de entrenamiento.

Consecuencia según la granularidad temporal (ver decisión abierta): si el dato es
anual, el modelado se recarga sobre la amplitud transversal (panel/jerárquico con
efectos de año) más que sobre el forecasting temporal. Si resulta haber datos
mensuales, el componente de pronóstico gana peso.

## 6. Alcance

**Dentro.** Panel municipal nacional del SNIIV; medida objetivo de §4; un modelo
con evaluación temporal honesta; API de servicio; tablero desplegado; pipeline de
ingesta/entrenamiento/monitoreo; contenedorización; tracking de experimentos.

**Fuera (por ahora).** Fuentes de banca (CNBV) más allá de Infonavit — Fase 2.
Precios de transacción / avalúos a nivel propiedad (no existen como microdato
público). Movilidad. Cualquier infraestructura pesada no justificada (ver §8).

## 7. Criterio de éxito

El modelo debe **superar a un baseline seasonal-naive y a un ETS fuera de
muestra, con validación temporal, no aleatoria**. Si no lo supera, el entregable
es el pipeline operativo, y se le llama por su nombre — no se disfraza el baseline
de ML.

## 8. Alcance de MLOps — del tamaño correcto

El rol objetivo es **ML Engineer full-stack**, no MLOps Engineer de plataforma.
En un mercado con casi cero talento de ML, el valor está en el generalista que
consigue el dato, modela, despliega y mantiene — no en la operación pura. Por
tanto: MLOps *suficiente*, no *máximo*.

- **Sí:** entorno reproducible, versionado de datos y modelo, tracking de
  experimentos (p. ej. MLflow), reentrenamiento programado, monitoreo de drift y
  de calidad/esquema de la fuente, contenedor (Docker), CI ligero, API servida.
- **No (dispersión disfrazada de rigor):** Kubernetes, Spark, feature stores a
  escala, orquestadores pesados. Coherente con la hoja de ruta previa.

## 9. Stack tentativo

Python 3.11, conda. pandas/numpy, requests para la ingesta. Modelado con
scikit-learn / gradient boosting y baselines de series (statsmodels). SQLite o
Parquet para el panel procesado. MLflow para tracking/registro. FastAPI para
servicio. Docker para contenedor. Tablero por definir. Sujeto a revisión al
avanzar; se adopta herramienta solo cuando el proyecto la exige.

## 10. Fases (alto nivel)

0. Andamiaje del repo (entorno, estructura, convenciones).
1. Contrato de ingesta y validación empírica de la fuente (checklist de §11).
2. Ingesta nacional reproducible + modelo de datos (panel municipio-periodo-segmento).
3. EDA del panel y baselines.
4. Modelo, evaluación temporal contra baselines, tracking.
5. Servicio (API) + contenedor.
6. Monitoreo, reentrenamiento programado, CI.
7. Tablero e indicadores de producto (incluida la brecha como salida).

Progresión secuencial, una decisión a la vez, con justificación explícita antes
de avanzar.

## 11. Bitácora de decisiones abiertas (por validar en el primer jalón real)

1. **¿La API acepta `mes`?** — pivote: define si el modelo es de panel o de
   forecasting. Confirmado hasta ahora: granularidad *anual*.
2. **¿Hasta qué año hay datos cargados?** — los ejemplos de la documentación
   llegan a 2022; falta confirmar 2024–2026.
3. **¿Se puede aislar adquisición vs. mejoramiento (Mejoravit) en Infonavit?**
   Si no, ¿el `monto` los mezcla? Riesgo de contaminación del target.
4. **Tope real de dimensiones por consulta** — 5 observado en ejemplos; sin
   confirmar como límite documentado.
5. **Alcance de fuente:** Infonavit-solo (recomendado para empezar) vs. incluir
   CNBV desde el inicio. Trade-off: Infonavit ignora el mercado de mayor valor.
6. **Nombre del repositorio.**

## 12. Fuentes de datos

- **SNIIV — CuboAPI** (SEDATU/Conavi): columna vertebral de la demanda financiada.
  Gramática `Get{Organismo}/{años}/{estado}/{municipio}/{dimensiones}`; medidas
  `acciones` y `monto`. Endpoints por organismo (INFONAVIT, FOVISSSTE, CNBV,
  CONAVI, Insus, FONHAPO) y agregado (Financiamiento).
- **Índice SHF de Precios de la Vivienda** (datos abiertos, CSV): ancla de precio
  a nivel municipal/ZM, basado en avalúos; para la brecha de asequibilidad.
- **INEGI**: features municipales (población, rezago, empleo) para el panel.
- **Pendiente de retomar:** Datos Masivos del SII (perfil del acreditado), cuando
  el servicio vuelva a estar disponible.

---

*Trampas del dato heredadas y vigentes: "valor de la vivienda" es un segmento
categórico, no pesos; "monto" es crédito, no valor de la vivienda, y topa en la
gama alta; los segmentos se indexan a UMA y se recorren por año.*

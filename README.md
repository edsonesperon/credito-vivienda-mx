# Observatorio de Vivienda Financiada

**Pronóstico municipal de demanda de crédito de vivienda Infonavit, con machine learning.**

Sistema integral de machine learning que estima, mes a mes y por municipio,
cuántos créditos de adquisición de vivienda Infonavit habrá en México. Cubre el
pipeline completo: ingesta de datos públicos, validación, modelado con evaluación
temporal honesta, tracking de experimentos y una API contenerizada que sirve el
pronóstico por HTTP.

> **Alcance, con precisión:** modela el crédito **Infonavit de adquisición**
> (`modalidad ∈ {Nueva, Existente}`) — el grueso de la vivienda formal de interés
> social y medio. No cubre crédito bancario ni compra al contado; la integración de
> CNBV (banca) es una extensión natural (ver *Trabajo futuro*).

## Resultado

- **El modelo le gana al baseline.** Un modelo global de gradient boosting baja el
  error (MASE) mediano de **1.00** (mejor baseline estadístico ETS) a **0.767**, y
  el medio de 1.10 a **0.839**, sobre los mismos 316 municipios y los mismos 12
  meses fuera de muestra. Le gana al mejor baseline en el **69.5%** de los municipios.
- **La estrategia de entrenamiento está validada, no asumida.** Un modelo entrenado
  con todo el país predice Mérida mejor (MASE **0.537**) que uno entrenado solo con
  Mérida (**0.961**) — el aprendizaje entre municipios transfiere. Esta comparación
  se construyó para poder *refutar* la hipótesis, no solo confirmarla.
- **Sirve en producción.** La API devuelve el pronóstico a 12 meses de cualquier
  municipio; empaquetada en una imagen Docker de servicio de ~103 MB (15x más
  liviana que si arrastrara el entorno de entrenamiento).

## Un hallazgo del dato

Entre 2015 y 2025, el número de créditos de adquisición a nivel nacional **cayó 7%**
mientras el monto en pesos **creció 2.35x**. El mercado de vivienda financiada no
crece en volumen: se encarece. Por eso el sistema pronostica el *conteo* de créditos
(la señal con estructura) y modela el precio por separado — una decisión de diseño
que salió del dato, no de un supuesto.

## Cómo está construido

```
Datos públicos (SNIIV/Infonavit)
      │  ingesta REST agnóstica a la fuente, con validación empírica
      ▼
Panel municipal mensual 2015-2026  (316 municipios elegibles, 97.7% del volumen)
      │  features anti-fuga temporal + baselines (seasonal-naive, ETS)
      ▼
Modelo global de gradient boosting  (evaluación temporal, tracking en MLflow)
      │  pronóstico de producción pre-computado
      ▼
API FastAPI  →  contenedor Docker
```

Detalle de cada decisión, con sus disyuntivas y las trampas del dato encontradas,
en [`docs/decisiones.md`](docs/decisiones.md).

## Cómo correrlo

```bash
# Entorno
conda env create -f environment.yml
conda activate credito-vivienda-mx

# Servir la API localmente (docs interactivas en http://127.0.0.1:8000/docs)
uvicorn api.main:app --reload

# O en contenedor
docker build -t credito-vivienda-mx .
docker run -p 8000:8000 credito-vivienda-mx
```

Consulta, por ejemplo, `GET /prediccion/31/50` para el pronóstico de Mérida.

El pipeline completo (ingesta → panel → modelo → tracking → pronóstico) se
reproduce corriendo los notebooks numerados de `notebooks/` en orden; cada uno
documenta qué hace y qué verifica en su encabezado.

## Qué demuestra este proyecto

- Pipeline de datos reproducible sobre una fuente pública real, con sus
  inconsistencias resueltas y **trece trampas del dato** documentadas.
- Evaluación honesta: validación temporal (nunca aleatoria), anti-fuga verificada
  por construcción, y una hipótesis de arquitectura sometida a una prueba que podía
  refutarla.
- Tramo de ML engineering completo: del dato crudo a un servicio desplegable, con
  tracking de experimentos y contenerización de servicio mínima.

## Trabajo futuro

Cada extensión es un proyecto con su propio arco, sobre esta misma base y metodología:

- **Integrar CNBV (crédito bancario):** la pieza que falta para pasar de "vivienda
  Infonavit" a "mercado de vivienda financiada" completo, incluido el segmento alto.
  La capa de ingesta ya se diseñó agnóstica a la fuente para admitirlo.
- **Tablero / web interactiva:** un frontend que consuma esta API y muestre el
  pronóstico de forma visual — pensado para un usuario no técnico (un desarrollador
  inmobiliario), no solo para `/docs`.
- **Monitoreo y CI:** detección de degradación del modelo, reentrenamiento
  programado y pruebas automáticas en cada cambio.
- **Mejorar la cola del modelo:** ~30% de municipios con MASE ≥ 1 (mercados con
  quiebres estructurales); target escalado por nivel y tratamiento de quiebres.

## Fuentes

- **SNIIV — CuboAPI** (SEDATU/Conavi): demanda de crédito financiado. Fuente principal.
- **Índice SHF de Precios de la Vivienda**: ancla de precio (asequibilidad).
- **INEGI**: features municipales.

Procedencia y trampas de cada fuente en [`docs/fuentes-y-procedencia.md`](docs/fuentes-y-procedencia.md).

## Contexto

Tercer proyecto de una línea sobre vivienda del sureste mexicano, y un salto
deliberado hacia ML engineering / MLOps: no solo modelar, sino ingerir, versionar,
servir y monitorear un modelo. El foco de despliegue es Mérida y el sureste; el
entrenamiento es nacional por diseño.

## Convenciones

- Progresión secuencial, una decisión a la vez, con justificación explícita.
- Código reutilizable en `src/`, exploración en `notebooks/`, servicio en `api/`.
- **Commits:** Conventional Commits — tipo en inglés + descripción en español,
  imperativa, minúscula, ≤50 caracteres.
- Rigor: citar fuentes, no inventar, marcar el nivel de confianza del dato,
  documentar las trampas.

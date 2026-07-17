# Bitácora de decisiones

Documento vivo. Registra qué se decidió, por qué, qué queda abierto y las
trampas del dato. Regla de la casa: no se anota como hecho nada que no se haya
verificado contra la fuente real.

---

## Decisiones cerradas

**D1 · Medida objetivo: monto de crédito de adquisición = acciones × ticket.**
Se modela en dos componentes (número de acciones y ticket promedio) en vez de
una sola bola de pesos, porque el ticket carga la señal de desplazamiento hacia
mayor valor, y separar "más créditos" de "créditos más caros" distingue dos
decisiones distintas para el usuario. Adquisición se define como
`modalidad ∈ {Nueva, Existente}` (ver T9). Se descartó la *brecha de
asequibilidad* como target de modelo: no tiene etiqueta medida contra la cual
validar; es un índice construido, y por tanto es la **salida** del producto, no
lo que el modelo aprende.

**D2 · Entrenamiento nacional, despliegue local — con salvedad de heterogeneidad.**
Se entrena sobre el panel nacional de municipios; Mérida y el sureste son foco de
despliegue, no el universo de entrenamiento. El pooling comparte la **dinámica**
(estacionalidad, respuesta a shocks macro, autocorrelación), no los **niveles**
(salarios, precio del suelo, volumen base), que se aíslan con un efecto por
municipio estimado con los propios datos de cada uno. Las diferencias de
composición (segmento, perfil) entran como features, no se promedian.
Salvedad reconocida: si la *dinámica misma* de Mérida difiere (pendientes
heterogéneas), el pooling le queda mal. No se asume que no: se prueba (ver D3b).
Nota: Mérida es rico en datos (136 meses, mediana 338), así que se sostiene casi
solo; el beneficio del pooling es mayor para los municipios marginales.

**D3 · Criterio de éxito PRIMARIO.** El modelo debe superar a un baseline
seasonal-naive y a un ETS, fuera de muestra, con validación temporal (no
aleatoria). Piso no negociable. Si no lo supera, el entregable honesto es el
pipeline operativo.

**D3b · Criterio de éxito SECUNDARIO (diagnóstico de transferibilidad).**
Comparar el modelo nacional contra uno entrenado solo con Mérida, ambos sobre los
mismos meses de Mérida fuera de muestra. Responde si la arquitectura de
entrenamiento nacional le sirve a Mérida o si Mérida es idiosincrática. Formal
pero secundario: no mide si el modelo sirve (eso es D3), mide si el rumbo de
entrenamiento fue el correcto. Cualquier resultado es un hallazgo, no un fracaso;
si Mérida gana en solitario, se pivota a modelo regional.

**D4 · Fuente inicial: Infonavit, con ingesta agnóstica a la fuente.** Se arranca
con `GetINFONAVIT` como columna vertebral (continuidad, volumen, cobertura
municipal limpia). La capa de ingesta se diseñó agnóstica a la fuente (registro
`ORGANISMOS`), de modo que CNBV entra como fuente #2 sin reescribir la mecánica.
Costo aceptado: Infonavit-solo ignora el mercado de mayor valor (banca), que
CNBV cubrirá después. Se descarta `GetFinanciamiento` agregado como target.

**D5 · Alcance de MLOps: del tamaño correcto.** Rol objetivo: ML Engineer
full-stack, no MLOps de plataforma. Suficiente para que un modelo modesto se
ingiera, versione, reentrene, sirva y monitoree de forma confiable. Se excluye
infraestructura pesada no justificada (Kubernetes, Spark, feature stores a
escala).

**D6 · SII de Infonavit: aparcado, y acotado a INGRESO.** La validación confirmó
que la CuboAPI SÍ expone la edad del acreditado (`grupo_edad`, ver T8) a nivel
municipal, por la vía automatizada. Pero el **ingreso en UMA NO existe** en la
CuboAPI (fantasma, ver T7). Conclusión: el SII deja de ser necesario para edad;
sigue siendo la única fuente para ingreso. Se integra solo si el ingreso resulta
imprescindible y cuando el servicio esté disponible; entraría como snapshot
manual de features de contexto, con la advertencia de su monto distinto.

**D7 · Unidad de análisis: panel mensual con umbral de volumen.** Umbral =
mediana ≥ 5 acciones de adquisición por mes. Derivado del barrido nacional, no a
ojo: con umbral 5 quedan **318 municipios (22%) que cubren 97.7% del volumen**
de adquisición; ~43,000 observaciones municipio-mes. Justificación del corte:
por debajo de 5/mes la serie es mayormente 1s, 2s y ceros (sin señal temporal
modelable); y el salto 1→2 muestra que ~920 municipios juntos aportan 0.5% del
volumen (ruido con forma de dato). Rango defendible 2-10; se eligió 5.
Los municipios bajo umbral NO se borran: se marcan `elegible=False` en
`dispersion_municipios.csv` para un eventual respaldo anual.

**D8 · Nombre del repositorio: `credito-vivienda-mx`.** Publicado. Se prefirió lo
genérico-pero-correcto sobre nombres con ambición inflada.

## Hallazgos confirmados contra la API (validación de la fuente)

- Datos de 2015 a 2026 (2026 parcial, a abril). Granularidad **mensual** (`mes`
  existe, devuelve el nombre del mes en español).
- Token de segmento: `valor_vivienda` — 7 valores, incluido "No disponible".
- Edad del acreditado: `grupo_edad` (4 rangos). Ingreso en UMA: no disponible.
- Sin tope práctico de dimensiones (≥7 aceptadas en una consulta).
- Features gratis en la respuesta: `clave_municipio` (llave INEGI, necesaria
  porque hay municipios homónimos, p. ej. dos "Juárez") y `zona`
  (Urbano/Rural/Semiurbano/Mixto).
- Composición nacional por modalidad: "Ampliación y rehabilitación" = 2.08M
  acciones (35% del total), casi igual que "Nueva" (2.15M).

## Trampas del dato

- **T1 · "valor de la vivienda" es segmento categórico, no pesos.** Indexado a UMA.
- **T2 · "monto" es crédito, no valor de la vivienda,** y topa en la gama alta.
- **T3 · Nombres de campo inconsistentes:** se pide `anio` y regresa `año`; se
  pide `genero` y regresa `sexo`; medidas como cadena o vacías. Lo maneja
  `normalizar_filas`.
- **T4 · (SII) El "monto" del Datos Masivos ≠ el de la CuboAPI:** total de recursos
  = crédito + saldo SCV − gastos de administración.
- **T5 · (SII) Granularidad aparentemente estatal, no municipal.**
- **T6 · (SII) Acceso por descarga manual,** sin API REST evidente.
- **T7 · La API NO ignora las dimensiones desconocidas: las sustituye por `zona`.**
  Una dimensión inexistente (`segmento`, `ingreso`, `uma`…) devuelve el desglose
  por `zona`, aparentando funcionar. La única detección fiable es comparar las
  LLAVES CRUDAS de la respuesta contra un baseline (ver `01_validacion_v2.py`).
- **T8 · `grupo_edad`: el nombre de request difiere del de respuesta.** Se pide
  `rango_edad`, la API responde bajo `grupo_edad`. Alias no trivial.
- **T9 · `modalidad` mezcla productos incomparables:** adquisición (Nueva,
  Existente) con mejoramiento (Ampliación y rehabilitación, 35% nacional, ticket
  ~$2,500), refinanciamiento (Pago de pasivos) y suelo. Sin filtrar a
  {Nueva, Existente}, el target queda contaminado. Contamina el "crédito
  promedio" de análisis previos que no filtraron.
- **T10 · Montos atípicos por modalidad:** "Autoconstrucción" trae monto = 0;
  "Ampliación" trae ticket ~$2,500 (sospecha de unidad o naturaleza distinta, a
  revisar). Ambas se excluyen del target de adquisición de todos modos.

## Pendientes

- **Umbral exacto:** cerrado en 5; revisable a 10 si el modelado pide series más
  robustas.
- **Features municipales de INEGI:** por definir cuáles y de qué tablas.
- **CNBV como fuente #2:** fase posterior (cubre el mercado de mayor valor).
- **SII para ingreso:** solo si resulta imprescindible y vuelve el servicio.

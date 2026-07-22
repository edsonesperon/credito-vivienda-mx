# Bitácora de decisiones

Documento vivo. Registra qué se decidió, por qué, qué queda abierto y las
trampas del dato. Regla de la casa: no se anota como hecho nada que no se haya
verificado contra la fuente real.

---

## Decisiones cerradas

**D1 · Medida objetivo: crédito de adquisición = acciones × ticket.**
Se modela en dos componentes en vez de una sola bola de pesos, porque el ticket
carga la señal de desplazamiento hacia mayor valor, y separar "más créditos" de
"créditos más caros" distingue dos decisiones distintas para el usuario.
Adquisición se define como `modalidad ∈ {Nueva, Existente}` (ver T9). Se descartó
la *brecha de asequibilidad* como target de modelo: no tiene etiqueta medida
contra la cual validar; es un índice construido, y por tanto es la salida del
producto, no lo que el modelo aprende.

**D1b · Target primario: `acciones`. Decidido por evidencia, no a priori.**
Los baselines de la Fase 3 mostraron que `monto` en pesos corrientes NO es
pronosticable de forma honesta (MASE > 1 en los tres métodos), mientras que
`acciones` sí (MASE mediano 0.760). La causa es estructural, no de método: entre
2015 y 2025 las acciones cayeron a 0.93x mientras el monto creció 2.35x — todo el
crecimiento en pesos es precio, cero volumen. Pronosticar `monto` directo mezcla
una serie de volumen plana con una de precio con deriva fuerte. El `ticket` se
modela aparte como componente de precio (en logs, deflactado o anclado a un
índice), y `monto` se recompone como producto. Esto confirma D1 con datos.

**D2 · Entrenamiento nacional, despliegue local — con salvedad de heterogeneidad.**
El pooling comparte la dinámica (estacionalidad, respuesta a shocks macro,
autocorrelación), no los niveles (salarios, precio del suelo, volumen base), que
se aíslan con un efecto por municipio estimado con sus propios datos. Las
diferencias de composición entran como features, no se promedian. Salvedad: si la
dinámica misma de Mérida difiere (pendientes heterogéneas), el pooling le queda
mal. No se asume que no: se prueba (D3b). Mérida es rico en datos (136 meses,
mediana 338 acciones/mes), así que se sostiene casi solo; el beneficio del pooling
es mayor para los municipios marginales.

**D3 · Criterio de éxito PRIMARIO.** El modelo debe superar el piso de baselines
fuera de muestra, con validación temporal (nunca aleatoria). Piso fijado en la
Fase 3: **MASE mediano 0.760 y medio 0.847** sobre `acciones` (ETS estacional sin
tendencia). Debe batirse en **ambas** estadísticas, no solo en la mediana, para
que el modelo no gane con un truco de centro mientras empeora la cola. Si no lo
supera, el entregable honesto es el pipeline operativo.

**D3b · Criterio de éxito SECUNDARIO (diagnóstico de transferibilidad).**
Comparar el modelo nacional contra uno entrenado solo con Mérida, ambos sobre los
mismos meses de Mérida fuera de muestra. Responde si la arquitectura de
entrenamiento nacional le sirve a Mérida o si Mérida es idiosincrática. Formal
pero secundario: no mide si el modelo sirve (eso es D3), mide si el rumbo de
entrenamiento fue el correcto. Cualquier resultado es un hallazgo; si Mérida gana
en solitario, se pivota a modelo regional.

**D4 · Fuente inicial: Infonavit, con ingesta agnóstica a la fuente.** Se arranca
con `GetINFONAVIT` como columna vertebral. La capa de ingesta se diseñó agnóstica
a la fuente (registro `ORGANISMOS`), de modo que CNBV entra como fuente #2 sin
reescribir la mecánica. Costo aceptado: Infonavit-solo ignora el mercado de mayor
valor (banca). Se descarta `GetFinanciamiento` agregado como target.

**D5 · Alcance de MLOps: del tamaño correcto.** Rol objetivo: ML Engineer
full-stack, no MLOps de plataforma. Suficiente para que un modelo modesto se
ingiera, versione, reentrene, sirva y monitoree de forma confiable. Se excluye
infraestructura pesada no justificada (Kubernetes, Spark, feature stores a escala).

**D6 · SII de Infonavit: aparcado, y acotado a INGRESO.** La CuboAPI expone la
edad del acreditado (`grupo_edad`, T8) a nivel municipal, por la vía automatizada.
El ingreso en UMA NO existe en la CuboAPI (fantasma, T7). El SII deja de ser
necesario para edad; sigue siendo la única fuente para ingreso. Se integra solo si
el ingreso resulta imprescindible y cuando el servicio esté disponible.

**D7 · Unidad de análisis: panel mensual con criterio DOBLE de elegibilidad.**
Elegible = mediana ≥ 5 acciones de adquisición/mes **Y** cobertura ≥ 0.5 (fracción
de meses con dato). Resultado: **316 municipios (22.0%) que cubren 97.7% del
volumen** de adquisición; ~43,000 observaciones municipio-mes.
El umbral de mediana salió del barrido nacional, no a ojo: por debajo de 5/mes la
serie es mayormente 1s, 2s y ceros, sin señal temporal modelable.
El piso de cobertura se agregó después, al descubrir que la mediana sola premia la
escasez (T12). Hace la mayor parte del filtrado: con cobertura ≥ 0.5 y mediana ≥ 1
quedan 526 municipios que ya cubren 99.5% del volumen.
Los municipios no elegibles NO se borran: quedan marcados en
`dispersion_municipios.csv` para un eventual respaldo anual.

**D8 · Nombre del repositorio: `credito-vivienda-mx`.** Publicado. Se prefirió lo
genérico-pero-correcto sobre nombres con ambición inflada.

**D9 · Regla de rellenado de ceros (corregida).** Se rellena con cero SOLO desde
la primera observación de cada municipio en adelante. Antes de esa primera
observación no se rellena: el municipio pudo no existir (T11). Después de la
primera observación, un mes ausente SÍ es cero real. El panel resultante es
desbalanceado a propósito: cada municipio empieza cuando empieza.

**D10 · Partición temporal:** últimos 12 meses (mayo 2025 a abril 2026) como
prueba fuera de muestra; el resto entrena. Doce meses dan un ciclo estacional
completo y manejan de forma natural el 2026 parcial. Nunca partición aleatoria.

## Hallazgos confirmados contra la API

- Datos de 2015 a 2026 (2026 parcial, a abril). Granularidad mensual (`mes`
  existe, devuelve el nombre del mes en español).
- Token de segmento: `valor_vivienda` — 7 valores, incluido "No disponible".
- Edad del acreditado: `grupo_edad` (4 rangos). Ingreso en UMA: no disponible.
- Sin tope práctico de dimensiones (≥7 aceptadas en una consulta).
- Features gratis en la respuesta: `clave_municipio` (llave INEGI, necesaria
  porque hay municipios homónimos, p. ej. dos "Juárez") y `zona`.
- Composición nacional por modalidad: "Ampliación y rehabilitación" = 2.08M
  acciones (35% del total), casi igual que "Nueva" (2.15M).
- **Volumen plano, precio al alza:** entre 2015 y 2025 las acciones de adquisición
  bajaron 7% (0.93x) mientras el monto creció 2.35x. El mercado no crece; se
  encarece. Lectura de producto: la pregunta útil no es "¿cuánto crecerá la
  demanda?" sino "¿hacia qué segmento y municipio se está moviendo la que existe?".

## Piso de baselines (Fase 3)

Evaluación fuera de muestra, 316 municipios, holdout de 12 meses, métrica MASE:

| target   | método             | mediana | media | p90   | % MASE<1 |
|----------|--------------------|---------|-------|-------|----------|
| acciones | seasonal_naive     | 0.937   | 0.988 | 1.545 | 56.0     |
| acciones | ets_sin_tendencia  | 0.760   | 0.847 | 1.301 | 71.8     |
| acciones | ets_con_tendencia  | 0.757   | 0.861 | 1.320 | 68.7     |
| monto    | seasonal_naive     | 1.524   | 1.595 | 2.388 | 14.2     |
| monto    | ets_sin_tendencia  | 1.273   | 1.357 | 2.139 | 28.8     |
| monto    | ets_con_tendencia  | 1.282   | 1.355 | 2.043 | 28.5     |

Se elige **ets_sin_tendencia** como piso formal: gana en media, p90 y porcentaje
de series batidas; su desventaja en mediana (0.003) es ruido.

## Trampas del dato

- **T1 · "valor de la vivienda" es segmento categórico, no pesos.** Indexado a UMA.
- **T2 · "monto" es crédito, no valor de la vivienda,** y topa en la gama alta.
- **T3 · Nombres de campo inconsistentes:** se pide `anio` y regresa `año`; se pide
  `genero` y regresa `sexo`; medidas como cadena o vacías.
- **T4 · (SII) El "monto" del Datos Masivos ≠ el de la CuboAPI:** total de recursos
  = crédito + saldo SCV − gastos de administración.
- **T5 · (SII) Granularidad aparentemente estatal, no municipal.**
- **T6 · (SII) Acceso por descarga manual,** sin API REST evidente.
- **T7 · La API NO ignora las dimensiones desconocidas: las sustituye por `zona`.**
  Una dimensión inexistente devuelve el desglose por `zona`, aparentando
  funcionar. La única detección fiable es comparar las llaves crudas de la
  respuesta contra un baseline (`01_validacion_v2.py`).
- **T8 · `grupo_edad`: el nombre de request difiere del de respuesta.** Se pide
  `rango_edad`, la API responde bajo `grupo_edad`.
- **T9 · `modalidad` mezcla productos incomparables:** adquisición (Nueva,
  Existente) con mejoramiento (Ampliación y rehabilitación, 35% nacional, ticket
  ~$2,500), refinanciamiento (Pago de pasivos) y suelo. Sin filtrar, el target
  queda contaminado. Contamina el "crédito promedio" de análisis previos que no
  filtraron.
- **T10 · Montos atípicos por modalidad:** "Autoconstrucción" trae monto = 0;
  "Ampliación" trae ticket ~$2,500. Ambas se excluyen del target de adquisición.
- **T11 · Municipios de creación reciente.** Villa de Pozos (SLP, clave 59) fue
  establecido el 23 de julio de 2024 por secesión del municipio de San Luis Potosí
  y empezó a gobernarse el 1 de octubre de 2024. Sus ceros de 2015-2024 no son
  "cero crédito": son "municipio inexistente". Rellenarlos fabricaba 118 meses de
  historia falsa y produjo un outlier de MASE 11.54 que parecía un hallazgo y era
  un bug. Corregido en D9. Nota: aparece en los datos de Infonavit desde 2025-03,
  con ~8 meses de rezago respecto al acto jurídico.
- **T12 · La mediana sobre celdas con dato premia la escasez.** Un municipio con 9
  meses de actividad en 8 años tiene mediana alta y pasaría el filtro, mientras
  uno con 130 meses de actividad baja no. Caso: Valle de Guadalupe (Jalisco),
  cobertura 0.066, mediana 14. Corregido con el piso de cobertura en D7.
- **T13 · El MASE está sesgado al alza en series con crecimiento multiplicativo.**
  El denominador se calcula con errores de años tempranos, cuando el nivel era
  mucho más bajo. Un MASE > 1 en `monto` no significa por sí solo que sea
  impronosticable: significa que medirlo en pesos corrientes con error absoluto es
  engañoso. Motiva D1b.

## Pendientes

- **Nueve municipios con quiebre estructural** (`quiebres_detectados.csv`): dos
  booms (Tolcayuca 3.20x, Playas de Rosarito 3.14x), seis colapsos (Tonanitla
  0.14, El Arenal 0.17, Juanacatlán 0.22, Xonacatlán 0.23, Nextlalpan 0.27,
  Tlacolula 0.29) y un corte final (San José Chiapa, deja de reportar en 2024-12).
  Son cambios de régimen reales, no errores. Decidir en Fase 4: excluir, truncar al
  régimen actual, o dar al modelo una variable que marque el quiebre.
- **Limitación del detector de quiebres:** compara la primera mitad del panel
  contra la segunda, así que es CIEGO a quiebres recientes — justo los que caen en
  el periodo de prueba. Por eso no detecta la caída de San Luis Potosí capital tras
  perder el territorio de Villa de Pozos. Mejorar antes de confiar en él como
  monitoreo.
- **Features municipales de INEGI:** por definir cuáles y de qué tablas.
- **CNBV como fuente #2:** fase posterior (cubre el mercado de mayor valor).
- **SII para ingreso:** solo si resulta imprescindible y vuelve el servicio.

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
decisiones distintas para el usuario. Se descartó la *brecha de asequibilidad*
como target de modelo: no tiene etiqueta medida contra la cual validar; es un
índice construido, y por tanto es la **salida** del producto, no lo que el modelo
aprende.

**D2 · Entrenamiento nacional, despliegue local.** Se entrena sobre el panel
nacional de municipios; Mérida y el sureste son foco de despliegue, no el
universo de entrenamiento. Restringir el entrenamiento a un municipio no
especializa: mata la señal (partial pooling). La especialización meridana vive
en dominio, producto y despliegue.

**D3 · Criterio de éxito.** El modelo debe superar a un baseline seasonal-naive
y a un ETS, fuera de muestra, con validación temporal (no aleatoria). Si no lo
supera, el entregable honesto es el pipeline operativo.

**D4 · Fuente inicial: Infonavit, con ingesta agnóstica a la fuente.** Se arranca
con `GetINFONAVIT` como columna vertebral (continuidad, volumen, cobertura
municipal limpia). La capa de ingesta se diseñó agnóstica a la fuente desde el
primer commit (registro `ORGANISMOS`), de modo que **CNBV entra como fuente #2**
(Fase 2) sin reescribir la mecánica. Costo aceptado: Infonavit-solo ignora el
mercado de mayor valor, que la banca (CNBV) cubrirá después. Se descarta
`GetFinanciamiento` agregado como target: mezcla organismos de semántica distinta
en un solo `monto`.

**D5 · Alcance de MLOps: del tamaño correcto.** Rol objetivo: ML Engineer
full-stack, no MLOps de plataforma. Suficiente para que un modelo modesto se
ingiera, versione, reentrene, sirva y monitoree de forma confiable. Se excluye
infraestructura pesada no justificada (Kubernetes, Spark, feature stores a
escala).

**D6 · SII de Infonavit: aparcado (no descartado).** El Datos Masivos del SII
aporta el perfil del acreditado (ingreso en UMA, edad), valioso para la
asequibilidad. Se aparca por tres razones verificadas (ver trampas T4-T6). Antes
de retomarlo, la validación dirá si la CuboAPI ya expone `rango_edad` y
`segmento_uma` a nivel municipio; si es así, el SII queda descartado para
siempre. Si no, entra como snapshot manual de features de contexto, nunca como
target.

## Decisiones abiertas (pendientes de la validación de la fuente)

- **A1 · ¿La API acepta `mes`?** Pivote del modelado: define si hay forecasting o
  solo panel transversal. Confirmado hasta ahora: granularidad anual.
- **A2 · ¿Hasta qué año hay datos cargados?** Los ejemplos oficiales llegan a 2022.
- **A3 · ¿Se aísla adquisición de mejoramiento (Mejoravit) en Infonavit?** Riesgo
  de contaminación del target si el `monto` los mezcla.
- **A4 · Tope real de dimensiones por consulta.** 5 observado en ejemplos; sin
  confirmar como límite documentado.
- **A5 · Token real de segmento** para Infonavit (`segmento` / `segmento_uma` /
  `valor_vivienda`).
- **A6 · Nombre del repositorio.** Candidato actual `credito-vivienda-mx`;
  alternativa preferida `observatorio-vivienda-mx`. Se cierra tras la validación,
  cuando la forma del proyecto deje de ser hipótesis.

## Trampas del dato

- **T1 · "valor de la vivienda" es segmento categórico, no pesos.** Se indexa a
  UMA y se recorre por año.
- **T2 · "monto" es crédito, no valor de la vivienda,** y topa en la gama alta.
- **T3 · Nombres de campo inconsistentes en la API:** se pide `anio` y a veces
  regresa `año`; se pide `genero` y regresa `sexo`; `acciones`/`monto` pueden
  venir como cadena o vacías. La normalización lo maneja (ver `src/ingesta_sniiv.py`).
- **T4 · (SII) El "monto" del Datos Masivos ≠ el de la CuboAPI.** En el SII es el
  *total de recursos transferidos* = monto de crédito + saldo de la Subcuenta de
  Vivienda − gastos de administración. No se pueden mezclar sin reconciliar.
- **T5 · (SII) Granularidad aparentemente estatal, no municipal.** Uniría al panel
  municipal solo por imputación, con pérdida de variación intraestatal.
- **T6 · (SII) Acceso por descarga manual** desde portal WebSphere, sin API REST
  evidente. En tensión con la tesis de pipeline automatizado.

# Fuentes y procedencia

Por cada fuente: qué aporta, cómo se accede, granularidad, periodicidad, nivel de
confianza y trampas. El nivel de confianza distingue lo **verificado** contra la
fuente real de lo **por confirmar** en la validación.

---

## 1. SNIIV — CuboAPI (SEDATU / Conavi) — columna vertebral

- **Qué aporta:** acciones (número de créditos) y monto de financiamiento a la
  vivienda, por organismo, geografía, año y otras dimensiones. Es la demanda
  financiada.
- **Acceso:** API REST pública que devuelve JSON.
  Gramática: `GET {BASE}/Get{Organismo}/{años}/{estado}/{municipio}/{dimensiones}`.
  Organismos con endpoint propio: INFONAVIT, FOVISSSTE, CNBV, CONAVI, Insus,
  FONHAPO; más el agregado `GetFinanciamiento`.
- **Medidas devueltas:** `acciones` y `monto` (siempre).
- **Granularidad geográfica:** municipal (clave INEGI; Yucatán `31`, Mérida `050`).
  **[verificado]**
- **Granularidad temporal:** anual confirmada en los ejemplos. Existencia de `mes`
  **[por confirmar — decisión A1]**.
- **Cobertura temporal:** los ejemplos oficiales llegan a 2022. Último año cargado
  **[por confirmar — A2]**.
- **Confianza:** alta en estructura y acceso (verificado contra ejemplos
  oficiales); media en cobertura y dimensiones legales (pendiente de validación).
- **Trampas:** ver T1, T2, T3 en `decisiones.md`.

## 2. Índice SHF de Precios de la Vivienda — ancla de precio (fase posterior)

- **Qué aporta:** nivel y tendencia de precio de la vivienda, para construir la
  brecha de asequibilidad (salida del producto, no target).
- **Base:** avalúos de vivienda adquirida con crédito hipotecario garantizado.
  Es valor de avalúo, no de lista ni de transacción individual.
- **Acceso:** datos abiertos en CSV (transparencia SHF).
- **Granularidad:** nacional, por entidad y por zonas metropolitanas/municipios
  grandes (Mérida cae en zona metropolitana). Es índice y distribución agregada,
  **no microdato por propiedad**.
- **Periodicidad:** trimestral.
- **Confianza:** media-alta (verificado en su naturaleza y disponibilidad; falta
  fijar el nivel geográfico exacto que usaremos).
- **Trampa:** al ser agregado, ancla el mercado, no valúa propiedades individuales.

## 3. INEGI — features municipales (fase posterior)

- **Qué aporta:** covariables del municipio para el panel (p. ej. población,
  rezago, empleo). Contexto que explica la demanda.
- **Acceso:** por definir (API/descarga según el indicador).
- **Granularidad:** municipal.
- **Confianza:** por definir — falta elegir las tablas/indicadores concretos.

## 4. SII de Infonavit — Datos Masivos — APARCADO (ver D6)

- **Qué aportaría:** perfil del acreditado — número de créditos por banda de
  ingreso en UMA y por grupo de edad. Señal de capacidad de pago para asequibilidad.
- **Acceso:** descarga manual desde el portal (WebSphere), en texto plano
  seleccionando variables. Sin API REST evidente. **[verificado]**
- **Granularidad:** aparentemente estatal (entidad federativa). **[por confirmar]**
- **Medida de monto:** *total de recursos transferidos* = monto de crédito + saldo
  de la Subcuenta de Vivienda − gastos de administración. **Distinta** de la
  CuboAPI. **[verificado en el descriptor oficial]**
- **Confianza:** alta en que existe y en su definición de monto; media en
  granularidad.
- **Estado:** no se integra hasta que la validación descarte que la CuboAPI ya
  cubre `rango_edad` y `segmento_uma` a nivel municipio (ver T4-T6 y D6).

---

*Nota: pendiente de retomar Datos Masivos del SII para el perfil del acreditado
solo si la vía automatizada (CuboAPI) no lo cubre.*

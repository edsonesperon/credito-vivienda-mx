# Contenedor MÍNIMO de servicio para el Observatorio de Vivienda Financiada.
#
# Sirve solo las predicciones pre-computadas (predicciones.csv) vía la API.
# NO incluye el stack de entrenamiento (scikit-learn, statsmodels, mlflow) ni los
# datos crudos ni los notebooks: la imagen de servicio y la de entrenamiento son
# cosas distintas, y separarlas mantiene este contenedor liviano y con una sola
# responsabilidad. El peso lo domina pandas; aun así queda muy por debajo de una
# imagen que arrastrara todo el entorno de modelado.

FROM python:3.11-slim

WORKDIR /app

# 1) Dependencias primero (capa cacheable): si el código cambia pero no las
#    dependencias, Docker reutiliza esta capa y no reinstala.
COPY api/requirements.txt ./api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt

# 2) Código de la API y la tabla de predicciones (lo único que el servicio sirve).
COPY api/ ./api/
COPY data/processed/predicciones.csv ./data/processed/predicciones.csv

# La API escucha en el 8000 dentro del contenedor.
EXPOSE 8000

# host 0.0.0.0 para que sea accesible desde fuera del contenedor (no solo localhost interno).
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

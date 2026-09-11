FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

# Sin esto el proceso corre como root: una ejecucion de codigo
# arbitrario dentro de la API seria root dentro del contenedor.
RUN useradd --system --no-create-home --uid 1001 stockarg \n    && chown -R stockarg:stockarg /app
USER stockarg

EXPOSE 8000

# El esquema se actualiza antes de aceptar trafico. Si una migracion
# falla el contenedor no arranca y la version anterior sigue sirviendo.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

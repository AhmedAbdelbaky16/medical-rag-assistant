# Used for both the api and frontend services (see docker-compose.yml)
# — same dependencies, different startup command per service.
#
# Uses Python 3.12 here regardless of what Python version you run
# locally on Windows. The container is fully isolated from your host
# Python, and 3.12 has universally available prebuilt wheels for every
# dependency in this project — sidesteps the Python-3.14-is-too-new
# wheel-building issues we hit earlier (lxml, psycopg2) without
# needing to solve them inside the container too.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY sql/ ./sql/

WORKDIR /app/src

EXPOSE 8000 8501

# Default command (used by the api service). The frontend service
# overrides this via `command:` in docker-compose.yml.
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]

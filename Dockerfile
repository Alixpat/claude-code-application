ARG DOCKER_REGISTRY

# Python application
FROM ${DOCKER_REGISTRY}/python:3.12-slim

ARG PIP_INDEX_URL

WORKDIR /app

# Layer 1: Python dependencies (changes rarely, cached)
COPY app/requirements.txt .
RUN pip install --no-cache-dir \
    --index-url "${PIP_INDEX_URL}" \
    --trusted-host "$(echo ${PIP_INDEX_URL} | sed 's|https\?://\([^/]*\).*|\1|')" \
    -r requirements.txt

# Layer 2: Static assets (changes rarely, cached separately)
COPY app/static/ ./static/

# Layer 3: Templates and application code (changes often)
COPY app/templates/ ./templates/
COPY app/main.py .

# Create uploads directory
RUN mkdir -p /app/uploads

EXPOSE 1000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "1000"]

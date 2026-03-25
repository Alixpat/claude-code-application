ARG DOCKER_REGISTRY
FROM ${DOCKER_REGISTRY}/python:3.12-slim

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

EXPOSE 1000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "1000"]

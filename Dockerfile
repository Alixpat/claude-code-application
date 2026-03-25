ARG DOCKER_REGISTRY
FROM ${DOCKER_REGISTRY}/python:3.12-slim

ARG PIP_INDEX_URL

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir \
    --index-url "${PIP_INDEX_URL}" \
    --trusted-host "$(echo ${PIP_INDEX_URL} | sed 's|https\?://\([^/]*\).*|\1|')" \
    --cert /etc/ssl/certs/ca-certificates.crt \
    -r requirements.txt

COPY app/ .

EXPOSE 1000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "1000"]

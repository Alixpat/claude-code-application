ARG DOCKER_REGISTRY

# Stage 1: Download DSFR assets
FROM ${DOCKER_REGISTRY}/node:22-alpine AS dsfr-builder
ARG NPM_REGISTRY
WORKDIR /build
RUN if [ -n "$NPM_REGISTRY" ]; then npm config set registry "$NPM_REGISTRY"; fi && \
    npm init -y && npm install @gouvfr/dsfr@1.12.1
RUN mkdir -p dsfr-dist && cp -r node_modules/@gouvfr/dsfr/dist/* dsfr-dist/

# Stage 2: Python application
FROM ${DOCKER_REGISTRY}/python:3.12-slim

ARG PIP_INDEX_URL

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir \
    --index-url "${PIP_INDEX_URL}" \
    --trusted-host "$(echo ${PIP_INDEX_URL} | sed 's|https\?://\([^/]*\).*|\1|')" \
    -r requirements.txt

COPY app/ .

# Copy DSFR assets from builder stage
COPY --from=dsfr-builder /build/dsfr-dist /app/static/dsfr

# Create uploads directory
RUN mkdir -p /app/uploads

EXPOSE 1000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "1000"]

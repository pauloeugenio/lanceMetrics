# syntax=docker/dockerfile:1
FROM --platform=$BUILDPLATFORM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY bare-metal/frontend/package.json bare-metal/frontend/package-lock.json ./
RUN npm ci
COPY bare-metal/frontend/ ./
RUN npm run build

# Target-platform Node keeps the original install.sh usable inside the image.
FROM node:22-bookworm-slim AS node-runtime
FROM python:3.12-slim-bookworm AS runtime
LABEL org.opencontainers.image.title="LANCE Metrics" \
    org.opencontainers.image.authors="Paulo Eugenio da Costa Filho <pauloeugenio@hotmail.com.br>" \
    org.opencontainers.image.vendor="Paulo Eugenio da Costa Filho" \
    org.opencontainers.image.url="https://github.com/pauloeugenio"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 LANCE_AUTH_ENABLED=false LANCE_BIND=0.0.0.0 LANCE_PORT=8080 \
    PATH="/app/.venv/bin:${PATH}"
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends bash iperf3 ffmpeg tini ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 lance \
    && useradd --uid 10001 --gid lance --create-home lance
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
WORKDIR /app
COPY bare-metal/backend/requirements.txt backend/requirements.txt
RUN python -m venv /app/.venv \
    && /app/.venv/bin/python -m pip install --no-cache-dir -r backend/requirements.txt \
    && /app/.venv/bin/python -m pip check
COPY --chown=lance:lance bare-metal/backend/ backend/
COPY --chown=lance:lance bare-metal/frontend/ frontend/
COPY --chown=lance:lance --from=frontend-build /build/frontend/dist/ frontend/dist/
COPY --chown=lance:lance bare-metal/examples/ examples/
COPY --chown=lance:lance bare-metal/lanceMetrics bare-metal/install.sh bare-metal/start.sh bare-metal/stop.sh ./
COPY --chown=lance:lance docker/docker-entrypoint.sh docker-entrypoint.sh
RUN sed -i 's/\r$//' lanceMetrics install.sh start.sh stop.sh docker-entrypoint.sh \
    && chmod +x lanceMetrics install.sh start.sh stop.sh docker-entrypoint.sh \
    && mkdir -p data/experiments data/profiles logs run \
    && chown -R lance:lance /app
USER lance
# Validate imports/tools on each target architecture without baking in a token/database.
RUN ./lanceMetrics diagnostics
EXPOSE 8080/tcp 5201/tcp 5201/udp 5000-5018/udp
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('LANCE_PORT','8080')+'/health',timeout=3)"
ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker-entrypoint.sh"]
CMD ["serve"]

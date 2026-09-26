FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY backend/ ./
RUN pip install --no-cache-dir . && useradd --system --uid 10001 punctual && mkdir /data && chown punctual /data
COPY --from=frontend /build/dist /app/static
ENV PUNCTUAL_DB=/data/punctual.db PUNCTUAL_STATIC=/app/static
USER punctual
EXPOSE 8000
CMD ["uvicorn", "punctual.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM python:3.12-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AI_USAGE_DATA=/data

RUN useradd --create-home --uid 1000 app \
 && mkdir -p /data /out \
 && chown app:app /data /out

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY ai_usage_monitor ./ai_usage_monitor
RUN pip install --no-cache-dir . && rm -rf /app/build

USER app
VOLUME ["/data", "/out"]
ENTRYPOINT ["python", "-m", "ai_usage_monitor"]
CMD ["demo", "--out", "/out"]

FROM app AS test
USER root
RUN pip install --no-cache-dir pytest
COPY tests ./tests
RUN chown -R app:app /app
USER app
ENTRYPOINT []
CMD ["python", "-m", "pytest", "-q"]

FROM app

FROM python:3.14.7-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /bin/uv
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --python /usr/local/bin/python
COPY src ./src
RUN uv sync --locked --no-dev --no-editable --python /usr/local/bin/python
RUN useradd --uid 10001 --create-home studio && mkdir /data && chown studio:studio /data
ENV PATH="/app/.venv/bin:$PATH" STUDIO_DATA_DIR=/data
USER studio
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "linksoul_studio.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]

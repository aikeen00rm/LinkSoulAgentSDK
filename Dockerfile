FROM python:3.14-slim
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.lock
COPY src ./src
RUN pip install --no-cache-dir --no-deps .
ENV STUDIO_DATA_DIR=/data
RUN useradd --uid 10001 --create-home studio && mkdir /data && chown studio:studio /data
USER studio
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "linksoul_studio.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]

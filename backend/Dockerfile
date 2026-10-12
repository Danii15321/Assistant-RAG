FROM python:3.10-slim@sha256:6ff506466f8b1e981719b468cc0023b8ef000b983cdec0eafe119d01f379e31d
ENV TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt \
    && python -c 'import tiktoken; tiktoken.get_encoding("o200k_harmony")' \
    && useradd --create-home --uid 1000 app \
    && mkdir -p /data/private && chown app:app /data/private && chmod 700 /data/private
COPY --chown=app:app . .
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "app"]

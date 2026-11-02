FROM python:3.14.9-slim-trixie@sha256:35caba83af2fe6da9a5d922f9b0156f21d1246a48278c58a08bd253303ba42e8
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY apps/api/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock && useradd --uid 10001 --create-home haven
COPY --chown=10001:10001 apps/api /app
COPY --chown=10001:10001 packages/crypto-core/bin/haven-public-verify-x86_64-linux /usr/local/bin/haven-public-verify
ENV MLS_PUBLIC_VERIFIER=/usr/local/bin/haven-public-verify
RUN test "$(uname -m)" = x86_64 && chmod 0555 /usr/local/bin/haven-public-verify
RUN python -m pip uninstall -y pip
USER 10001:10001
EXPOSE 8100
CMD ["python", "-m", "haven.server", "--host", "0.0.0.0", "--forwarded-allow-ips", "*"]

FROM python:3.15.0-slim-trixie@sha256:f5b92f2a669a4c347044f29367f31983280b648250ca94dea66f98c53bc87e58
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
CMD ["uvicorn", "haven.asgi:application", "--host", "0.0.0.0", "--port", "8100", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "*", "--ws-max-size", "2048"]

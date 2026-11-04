# Supply only the public signed release through the client_release named context.
FROM python:3.14.9-slim-trixie@sha256:35caba83af2fe6da9a5d922f9b0156f21d1246a48278c58a08bd253303ba42e8
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY apps/verified-client/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock && useradd --uid 10001 --create-home haven-client
COPY apps/verified-client/trust/release.pub /app/release.pub
COPY apps/verified-client/runtime/haven_client/release.py /app/release.py
COPY apps/verified-client/server-entrypoint.py /app/server-entrypoint.py
COPY --from=client_release release.haven /app/release.haven
ARG CLIENT_MINIMUM_SEQUENCE
RUN test -n "$CLIENT_MINIMUM_SEQUENCE" && printf '%s\n' "$CLIENT_MINIMUM_SEQUENCE" > /app/minimum-sequence && python -I /app/server-entrypoint.py --prepare-image
RUN python -m pip uninstall -y pip
USER 10001:10001
EXPOSE 8447
ENTRYPOINT ["python", "-I", "/app/server-entrypoint.py"]

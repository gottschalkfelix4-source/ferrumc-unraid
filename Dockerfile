# syntax=docker/dockerfile:1
FROM alpine:3.23 AS download
RUN apk add --no-cache ca-certificates curl
ARG TARGETARCH
COPY docker/upstream.json /tmp/upstream.json
COPY docker/download.sh /usr/local/bin/download-ferrumc
RUN apk add --no-cache jq && sh /usr/local/bin/download-ferrumc

FROM python:3.13-alpine3.23
ARG VERSION=v0.1.0-rc2
ARG REVISION=unknown
LABEL org.opencontainers.image.title="FerrumC for Unraid" \
      org.opencontainers.image.description="FerrumC with its built-in dashboard and persistent Unraid storage" \
      org.opencontainers.image.source="https://github.com/gottschalkfelix4-source/ferrumc-unraid" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"
RUN apk add --no-cache ca-certificates tzdata
COPY requirements.txt /opt/ferrumc/requirements.txt
RUN pip install --no-cache-dir -r /opt/ferrumc/requirements.txt
COPY --from=download /out/ferrumc /opt/ferrumc/ferrumc
COPY docker/entrypoint.py docker/healthcheck.py docker/minecraft_status.py /opt/ferrumc/
COPY docker/upstream.json LICENSE LICENSE.ferrumc /opt/ferrumc/
ENV PUID=99 PGID=100 UMASK=002 LOG_LEVEL=info PYTHONUNBUFFERED=1
WORKDIR /data
VOLUME ["/data"]
EXPOSE 25565/tcp 9000/tcp
# FerrumC registers a Ctrl-C handler that saves the world before exiting.
STOPSIGNAL SIGINT
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD ["python", "/opt/ferrumc/healthcheck.py"]
ENTRYPOINT ["python", "/opt/ferrumc/entrypoint.py"]
CMD ["run"]

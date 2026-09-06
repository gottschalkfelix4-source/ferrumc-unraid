# syntax=docker/dockerfile:1
FROM node:24-alpine3.23 AS dashboard
RUN npm install --global pnpm@11.19.0
WORKDIR /ui
COPY dashboard/package.json dashboard/pnpm-lock.yaml dashboard/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY dashboard/ ./
RUN pnpm check && pnpm build

FROM rust:1-bookworm AS server
RUN rustup toolchain install nightly-2026-09-01 --profile minimal --component rustfmt
WORKDIR /src
ADD https://codeload.github.com/ferrumc-rs/ferrumc/tar.gz/8054bc4ee5add21e0438258a8b0444b5c36dc90f /tmp/source.tar.gz
RUN echo '0af3970302cd2070fa6a97d9b67ea242b1cdd7606b83fe9f8f1d7eb24f5a17d1  /tmp/source.tar.gz' | sha256sum -c - \
    && tar xzf /tmp/source.tar.gz --strip-components=1 && rm /tmp/source.tar.gz
COPY patches/ /patches/
RUN git apply /patches/ferrumc.patch \
    && cp /patches/bridge.rs src/lib/dashboard/src/bridge.rs \
    && cp /patches/bans.rs src/lib/config/src/bans.rs \
    && cp /patches/Cargo.lock Cargo.lock
RUN cargo +nightly-2026-09-01 build --locked --release -p ferrumc --features release -j 2 \
    && strip target/release/ferrumc

FROM python:3.13-slim-bookworm
ARG VERSION=v0.1.0-rc2-dashboard.1
ARG REVISION=unknown
LABEL org.opencontainers.image.title="FerrumC for Unraid" \
      org.opencontainers.image.description="FerrumC with an authenticated management dashboard and persistent Unraid storage" \
      org.opencontainers.image.source="https://github.com/gottschalkfelix4-source/ferrumc-unraid" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates tzdata && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /opt/ferrumc/requirements.txt
RUN pip install --no-cache-dir -r /opt/ferrumc/requirements.txt
COPY --from=server /src/target/release/ferrumc /opt/ferrumc/ferrumc
COPY --from=dashboard /ui/build /opt/ferrumc/dashboard
COPY docker/entrypoint.py docker/manager.py docker/healthcheck.py docker/minecraft_status.py /opt/ferrumc/
COPY docker/upstream.json LICENSE LICENSE.ferrumc /opt/ferrumc/
ENV PUID=99 PGID=100 UMASK=002 LOG_LEVEL=info PYTHONUNBUFFERED=1
WORKDIR /data
VOLUME ["/data"]
EXPOSE 25565/tcp 9000/tcp
STOPSIGNAL SIGINT
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD ["python", "/opt/ferrumc/healthcheck.py"]
ENTRYPOINT ["python", "/opt/ferrumc/entrypoint.py"]
CMD ["run"]

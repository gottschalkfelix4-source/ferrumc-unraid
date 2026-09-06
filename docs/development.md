# Dashboard development

This repository extends the official FerrumC dashboard, retaining its Svelte components, colors and typography. It is an independent community build. It does not change Minecraft's supported protocol (Java 1.21.8 / 772).

## Components

- `dashboard/`: static SvelteKit application. `pnpm install --frozen-lockfile`, `pnpm check`, `pnpm build` produce `dashboard/build/`.
- `docker/manager.py`: aiohttp HTTP/WebSocket API and process supervisor. It owns authentication, lifecycle, bounded console output, configuration writes, access-list files and SQLite history. It runs under PUID/PGID and has no Docker socket access.
- `patches/ferrumc.patch`: changes against the exact release commit in `docker/upstream.json`. It replaces the upstream dashboard asset download with an internal API, connects dashboard commands to the real ECS tick, measures ticks, enforces bans/whitelist during authenticated login, and flushes rejection packets before closing a connection.
- `patches/bridge.rs`: copied into `src/lib/dashboard/src/bridge.rs` before compilation. Commands use a bounded queue and the existing command registry; player operations use real server state.
- `patches/bans.rs`: copied into `src/lib/config/src/bans.rs`. It reads the ban list on every login. An unreadable or malformed ban file rejects logins.
- `patches/Cargo.lock`: exact native dependency resolution. The Dockerfile pins the Rust nightly and verifies the source archive SHA256.

The public dashboard listens on container port 9000. The native bridge only listens on `127.0.0.1:9001` **inside the container**. Do not publish the bridge, mount the Docker socket, or point the manager at an untrusted bridge. Stop/start changes the child Minecraft process; the dashboard stays available. Container shutdown closes dashboard connections and sends SIGINT to the child, with a bounded graceful shutdown period.

## Public API

All `/api/*` routes except `login` and `session` require the dashboard session cookie. Mutations additionally require `X-FerrumC-Request: dashboard`; any supplied Origin must match the request origin. `/ws` requires both the cookie and the exact Origin. For TLS termination at a reverse proxy, set `DASHBOARD_ORIGIN` to the explicit public origin; this also enables Secure cookies. Forwarded headers alone are not trusted. The UI uses same-origin URLs, so host port remapping needs no separate WebSocket configuration.

| Route | Method | Purpose |
| --- | --- | --- |
| `/api/login` | POST | `{password}`; sets HttpOnly, SameSite=Strict cookie |
| `/api/session` | GET | Authentication state |
| `/api/logout` | POST | Invalidates the session, including live sockets |
| `/api/state` | GET | Server state, freshness, real metrics/players and pending restart |
| `/api/config` | GET / PUT | Supported values and a revision hash; PUT requires `{values, revision}` |
| `/api/power` | POST | `{action: "start" / "stop" / "restart"}`; returns 202 when accepted |
| `/api/command` | POST | `{command}`; queues one ASCII console command |
| `/api/players/{uuid}/kick` | POST | `{reason}` |
| `/api/lists` | GET | Stored ban and whitelist UUIDs |
| `/api/lists/{bans\|whitelist}` | POST | `{uuid, action: "add" / "remove"}` |
| `/api/history?range=1h` | GET | 1h, 6h or 24h measured TPS/MSPT history |
| `/api/logs/download` | GET | Most recent 2,000 console lines as text |
| `/ws` | WebSocket | `State` events with state and incremental console lines |
| `/healthz` | GET | Public minimal liveness result; an intentionally stopped server is healthy |

A successful config save writes `configs/config.toml.bak` and `.dashboard-config-managed`. On later container starts, dashboard-managed game settings take precedence over environment defaults. Internal addresses/ports remain fixed. Config edits preserve unknown TOML fields/comments. Saving with a stale revision returns 409.

Whitelist files use UUIDs, optionally followed by `# comments`. Updates affect subsequent connections. They do not disconnect current players; use Kick for that. Ban additions also disconnect matching online players. Minecraft account authentication stays enabled by default.

## Tests

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
pnpm --dir dashboard install --frozen-lockfile
pnpm --dir dashboard check
pnpm --dir dashboard build
npm ci --prefix tests/client
docker build -t ferrumc-unraid:local .
python3 tests/container_smoke.py ferrumc-unraid:local
```

Node.js 24 is used for the Minecraft protocol client. The container test creates its own disposable volume and random dashboard password. It tests real Minecraft packets, authenticated WebSockets, commands actually dispatched in the native ECS, config conflict handling, graceful power operations, real player kick/ban/whitelist enforcement, non-root ownership, and persistence across container recreation. It never needs a Mojang account: it temporarily configures **its isolated test server** for offline login and restores the previous settings afterward.

`tests/dashboard_probe.py` and `tests/client/players.cjs` also work against a local development instance. They mutate configuration and player lists, so run them only against a dedicated test world. Supported manager development overrides are `FERRUMC_DATA`, `FERRUMC_BINARY`, `DASHBOARD_STATIC`, `DASHBOARD_HOST`, `DASHBOARD_PORT`, and `FERRUMC_BRIDGE_PORT`. Minecraft's container-side port remains 25565.

## Upstream upgrades

Update the pinned commit/archive hash, regenerate the patch against a clean upstream checkout, refresh the lockfile using the pinned compiler and check the Minecraft protocol tests. Review upstream command parsing, login ordering, lifecycle and ECS message handling explicitly. Never build an unpinned development branch as `latest`. GitHub Actions publishes the shared manifest only after both native architecture tests pass.

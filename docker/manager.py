"""Authenticated dashboard API and FerrumC process supervisor (no Docker socket)."""
import asyncio
from collections import deque
import contextlib
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import signal
import sqlite3
import time
import tomllib
import uuid

from aiohttp import ClientError, ClientSession, ClientTimeout, WSMsgType, web
import tomlkit

from entrypoint import atomic_write

FIELDS = {"motd", "max_players", "chunk_render_distance", "online_mode", "whitelist",
          "default_gamemode", "tps", "network_compression_threshold", "encryption_enabled"}
ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def validate_config(values):
    if not isinstance(values, dict) or set(values) != FIELDS:
        raise ValueError("Send all supported configuration fields")
    for key, low, high in (("max_players", 1, 10000), ("chunk_render_distance", 2, 32),
                           ("tps", 1, 100), ("network_compression_threshold", -1, 1048576)):
        if type(values[key]) is not int or not low <= values[key] <= high:
            raise ValueError(f"{key} must be an integer between {low} and {high}")
    for key in ("online_mode", "whitelist", "encryption_enabled"):
        if type(values[key]) is not bool:
            raise ValueError(f"{key} must be true or false")
    if values["default_gamemode"] not in ("creative", "survival", "adventure", "spectator"):
        raise ValueError("Invalid game mode")
    if not isinstance(values["motd"], list) or not 1 <= len(values["motd"]) <= 20 or any(
            not isinstance(line, str) or not 1 <= len(line) <= 512 for line in values["motd"]):
        raise ValueError("Supply 1–20 server messages, each with 1–512 characters")
    return values


class Manager:
    def __init__(self, data, binary, static, bridge_port=9001):
        self.data, self.binary, self.static = Path(data), Path(binary), Path(static).resolve()
        self.bridge = f"http://127.0.0.1:{bridge_port}"
        self.bridge_port = bridge_port
        self.proc = None
        self.output_task = None
        self.status = "Stopped"
        self.last_exit = None
        self.logs = deque(maxlen=2000)
        self.sequence = 0
        self.instance = secrets.token_hex(8)
        self.metrics = {}
        self.handshake = {}
        self.players = []
        self.clients = set()
        self.sessions = {}
        self.failures = {}
        self.lock = asyncio.Lock()
        self.tasks = []
        self.operation = None
        self.closing = False
        self.pending_config = False
        self.running_config = None
        self.last_metric = 0.0
        self.started_at = 0.0
        self.last_sample = 0.0
        self.last_network = None
        self.password = self.load_password()
        self.db = sqlite3.connect(self.data / "dashboard-metrics.sqlite3")
        self.db.execute("CREATE TABLE IF NOT EXISTS metrics (time INTEGER PRIMARY KEY, tps REAL, mspt REAL, cpu REAL, ram INTEGER)")

    def load_password(self):
        password = os.environ.get("DASHBOARD_PASSWORD", "")
        path = self.data / "dashboard-password.txt"
        if not password:
            if not path.exists():
                atomic_write(path, secrets.token_urlsafe(24) + "\n")
                path.chmod(0o600)
            password = path.read_text().strip()
        if len(password) < 12:
            raise ValueError("DASHBOARD_PASSWORD must contain at least 12 characters")
        print("Dashboard login enabled. Set DASHBOARD_PASSWORD in Unraid or read /data/dashboard-password.txt.", flush=True)
        return hashlib.sha256(password.encode()).digest()

    def add_log(self, message, level=None):
        message = ANSI.sub("", message).strip()[:4096]
        if not message:
            return
        self.sequence += 1
        match = re.search(r"\b(TRACE|DEBUG|INFO|WARN|ERROR)\b", message)
        self.logs.append({"id": self.sequence, "time": int(time.time() * 1000),
                          "level": level or (match.group(1) if match else "INFO"), "message": message})
        print(message, flush=True)

    async def read_output(self, process):
        buffer = b""
        while chunk := await process.stdout.read(4096):
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                self.add_log(line.decode(errors="replace"))
            if len(buffer) > 16384:
                self.add_log(buffer[:4096].decode(errors="replace") + " [truncated]")
                buffer = b""
        if buffer:
            self.add_log(buffer.decode(errors="replace"))
        code = await process.wait()
        if self.proc is process:
            self.last_exit = code
            if self.status not in ("Stopping", "Restarting"):
                self.status = "Stopped" if code == 0 else "Failed"
            self.players = []
            self.metrics = {}
            self.add_log(f"FerrumC exited with code {code}", "INFO" if code == 0 else "ERROR")

    async def start(self):
        if self.proc and self.proc.returncode is None:
            return
        self.status = "Starting"
        self.started_at = time.monotonic()
        self.tasks = [task for task in self.tasks if not task.done()]
        env = dict(os.environ, FERRUMC_BRIDGE_PORT=str(self.bridge_port), NO_COLOR="1")
        # The child does not need the dashboard administrator password.
        env.pop("DASHBOARD_PASSWORD", None)
        self.running_config = self.config_values()
        self.pending_config = False
        self.proc = await asyncio.create_subprocess_exec(str(self.binary), "--log",
                    os.environ.get("LOG_LEVEL", "info"), "run", cwd=self.data, env=env,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        self.output_task = asyncio.create_task(self.read_output(self.proc))
        self.tasks.append(self.output_task)

    async def stop(self):
        process = self.proc
        if process and process.returncode is None:
            self.status = "Stopping"
            process.send_signal(signal.SIGINT)
            try:
                await asyncio.wait_for(process.wait(), timeout=110)
            except asyncio.TimeoutError:
                self.add_log("Graceful shutdown timed out; forcing termination", "ERROR")
                process.kill()
                await process.wait()
        if self.output_task:
            await self.output_task
        self.status = "Stopped"
        self.last_metric = 0.0
        self.players, self.metrics = [], {}

    async def power(self, action):
        async with self.lock:
            try:
                if action in ("stop", "restart"):
                    await self.stop()
                if action in ("start", "restart") and not self.closing:
                    await self.start()
            except Exception:
                self.status = "Failed"
                self.add_log("Server operation failed. Check permissions and configuration.", "ERROR")
            finally:
                self.operation = None

    async def native(self, method, path, payload=None):
        if not self.proc or self.proc.returncode is not None:
            raise web.HTTPConflict(text="The Minecraft server is stopped")
        try:
            async with self.http.request(method, self.bridge + "/api" + path, json=payload) as response:
                if response.status >= 400:
                    exception = {404: web.HTTPNotFound, 409: web.HTTPConflict,
                                 429: web.HTTPTooManyRequests}.get(response.status, web.HTTPBadRequest)
                    raise exception(text=await response.text())
                return await response.json()
        except (ClientError, OSError, asyncio.TimeoutError):
            raise web.HTTPServiceUnavailable(text="Server is still starting or unavailable") from None

    async def collect(self):
        while not self.closing:
            try:
                if not self.proc or self.proc.returncode is not None:
                    await asyncio.sleep(1)
                    continue
                async with self.http.ws_connect(self.bridge + "/ws", heartbeat=15) as socket:
                    async for message in socket:
                        if message.type != WSMsgType.TEXT:
                            continue
                        event = json.loads(message.data)
                        if event["type"] == "Handshake":
                            self.handshake = event["data"]
                        elif event["type"] == "Metric":
                            self.metrics = event["data"]
                            self.last_metric = time.monotonic()
                            if self.status == "Starting":
                                self.status = "Running"
                            self.players = await self.native("GET", "/players")
                            self.network_rates()
                            now = int(time.time())
                            if now - self.last_sample >= 5:
                                m = self.metrics
                                self.db.execute("INSERT OR REPLACE INTO metrics VALUES (?,?,?,?,?)",
                                    (now, m.get("tps"), m.get("mspt"), m.get("cpu_usage"), m.get("ram_usage")))
                                self.db.execute("DELETE FROM metrics WHERE time < ?", (now - 86400,))
                                self.db.commit()
                                self.last_sample = now
            except (ClientError, OSError, asyncio.TimeoutError, web.HTTPException, ValueError):
                self.players = []
                await asyncio.sleep(1)

    def network_rates(self):
        try:
            lines = Path(f"/proc/{self.proc.pid}/net/dev").read_text().splitlines()[2:]
            receive = send = 0
            for line in lines:
                interface, raw = line.split(":", 1)
                if interface.strip() == "lo":
                    continue
                fields = raw.split()
                receive += int(fields[0]); send += int(fields[8])
            now = time.monotonic()
            if self.last_network:
                previous, rx, tx = self.last_network
                self.metrics.update(network_rx=max(0, receive-rx)/(now-previous),
                                    network_tx=max(0, send-tx)/(now-previous))
            self.last_network = now, receive, send
        except (OSError, ValueError, IndexError):
            self.metrics.update(network_rx=None, network_tx=None)

    def state(self):
        fresh = self.status == "Running" and time.monotonic() - self.last_metric < 5
        return {"instance": self.instance, "status": self.status, "fresh": fresh, "metrics": self.metrics if fresh else {},
                "system": self.handshake.get("system", {}), "config": self.handshake.get("config", {}),
                "players": self.players if fresh else [], "pending_config": self.pending_config,
                "operation": self.operation, "last_exit": self.last_exit}

    def config_values(self):
        config = tomllib.loads((self.data / "configs/config.toml").read_text())
        return {key: config[key] for key in FIELDS}

    def authorized(self, request):
        return self.sessions.get(request.cookies.get("ferrumc_session", ""), 0) > time.monotonic()

    @web.middleware
    async def security(self, request, handler):
        try:
            if request.method not in ("GET", "HEAD"):
                if request.headers.get("X-FerrumC-Request") != "dashboard":
                    raise web.HTTPForbidden(text="Missing request protection")
                origin = request.headers.get("Origin")
                if origin and origin != f"{request.scheme}://{request.host}":
                    raise web.HTTPForbidden(text="Cross-origin requests are not allowed")
            if request.path == "/ws":
                if request.headers.get("Origin") != f"{request.scheme}://{request.host}":
                    raise web.HTTPForbidden(text="Cross-origin WebSocket rejected")
            if (request.path.startswith("/api/") and request.path not in ("/api/login", "/api/session")) or request.path == "/ws":
                if not self.authorized(request):
                    raise web.HTTPUnauthorized(text="Sign in to manage FerrumC")
            response = await handler(request)
        except web.HTTPException as error:
            response = web.json_response({"error": error.text or error.reason}, status=error.status if error.status >= 400 else 400)
        except (ValueError, KeyError, TypeError, tomlkit.exceptions.ParseError):
            response = web.json_response({"error": "Invalid request or configuration values"}, status=400)
        response.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"})
        return response

    async def login(self, request):
        remote = request.remote or "unknown"
        now = time.monotonic()
        self.failures = {k:v for k,v in self.failures.items() if now-v[1] < 60}
        count, _ = self.failures.get(remote, (0, now))
        if count >= 8 or len(self.failures) >= 1024:
            raise web.HTTPTooManyRequests(text="Too many attempts. Try again in one minute.")
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("Expected a JSON object")
        password = body.get("password", "")
        if not isinstance(password, str) or not hmac.compare_digest(hashlib.sha256(password.encode()).digest(), self.password):
            self.failures[remote] = count + 1, now
            raise web.HTTPUnauthorized(text="Incorrect dashboard password")
        self.failures.pop(remote, None)
        self.sessions = {k:v for k,v in self.sessions.items() if v > now}
        if len(self.sessions) >= 128:
            self.sessions.pop(next(iter(self.sessions)))
        token = secrets.token_urlsafe(32)
        self.sessions[token] = now + 43200
        response = web.json_response({"authenticated": True})
        response.set_cookie("ferrumc_session", token, httponly=True, secure=request.secure,
                            samesite="Strict", max_age=43200, path="/")
        return response

    async def logout(self, request):
        self.sessions.pop(request.cookies.get("ferrumc_session", ""), None)
        response = web.json_response({"ok": True})
        response.del_cookie("ferrumc_session", path="/")
        return response

    async def session(self, request):
        return web.json_response({"authenticated": self.authorized(request)})

    async def get_state(self, request):
        return web.json_response(self.state())

    async def websocket(self, request):
        if len(self.clients) >= 32:
            raise web.HTTPTooManyRequests(text="Too many dashboard connections")
        ws = web.WebSocketResponse(heartbeat=20, timeout=2, max_msg_size=4096)
        await ws.prepare(request)
        self.clients.add(ws)
        last_id = 0
        try:
            while not ws.closed and not self.closing and self.authorized(request):
                await asyncio.wait_for(ws.send_json({"type": "State", "data": self.state(),
                    "logs": [line for line in self.logs if line["id"] > last_id]}), 5)
                last_id = self.sequence
                try:
                    message = await ws.receive(timeout=1)
                    if message.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                        break
                except asyncio.TimeoutError:
                    pass
        except (ConnectionError, asyncio.TimeoutError):
            pass
        finally:
            self.clients.discard(ws)
            await ws.close()
        return ws

    async def get_config(self, request):
        text = (self.data / "configs/config.toml").read_text()
        return web.json_response({"values": self.config_values(),
            "revision": hashlib.sha256(text.encode()).hexdigest(), "pending_restart": self.pending_config,
            "managed": (self.data / ".dashboard-config-managed").exists()})

    async def save_config(self, request):
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("Expected a JSON object")
        values = validate_config(body["values"])
        async with self.lock:
            path = self.data / "configs/config.toml"
            before = path.read_text()
            if body.get("revision") != hashlib.sha256(before.encode()).hexdigest():
                raise web.HTTPConflict(text="Configuration changed elsewhere. Reload before saving.")
            config = tomlkit.parse(before)
            for key, value in values.items():
                config[key] = value
            atomic_write(path.with_suffix(".toml.bak"), before)
            atomic_write(self.data / ".dashboard-config-managed", "Dashboard settings take precedence over environment defaults.\n")
            atomic_write(path, tomlkit.dumps(config))
            self.pending_config = values != self.running_config
            self.add_log("Dashboard configuration saved; restart to apply")
        return await self.get_config(request)

    async def power_action(self, request):
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("Expected a JSON object")
        action = body.get("action")
        if action not in ("start", "stop", "restart"):
            raise ValueError("Invalid power action")
        if self.operation or self.closing:
            raise web.HTTPConflict(text="Another server operation is already running")
        self.operation = action
        self.tasks.append(asyncio.create_task(self.power(action)))
        return web.json_response({"accepted": True, "action": action}, status=202)

    async def command(self, request):
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("Expected a JSON object")
        if not isinstance(body.get("command"), str):
            raise ValueError("Missing command")
        command = body["command"].strip().lstrip("/")
        if command in ("stop", "restart", "start"):
            raise web.HTTPBadRequest(text="Use Power Options to start, stop or restart the server")
        return web.json_response(await self.native("POST", "/command", {"command": command}))

    async def kick(self, request):
        identifier = str(uuid.UUID(request.match_info["uuid"]))
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("Expected a JSON object")
        reason = body.get("reason", "Disconnected by an administrator")
        if not isinstance(reason, str) or len(reason) > 256:
            raise ValueError("Invalid reason")
        return web.json_response(await self.native("POST", f"/players/{identifier}/kick", {"reason": reason}))

    def read_list(self, kind):
        path = self.data / ("banned-players.json" if kind == "bans" else "whitelist.txt")
        if not path.exists():
            return []
        if kind == "bans":
            return json.loads(path.read_text())
        result = []
        for line in path.read_text().splitlines():
            value = line.split("#", 1)[0].strip()
            if value:
                # Preserve existing username entries; additions through this API use UUIDs.
                result.append(value)
        return result

    async def lists(self, request):
        return web.json_response({"bans": self.read_list("bans"), "whitelist": self.read_list("whitelist")})

    async def change_list(self, request):
        kind = request.match_info["kind"]
        if kind not in ("bans", "whitelist"):
            raise web.HTTPNotFound()
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("Expected a JSON object")
        identifier = str(uuid.UUID(body["uuid"]))
        if body.get("action") not in ("add", "remove"):
            raise ValueError("Invalid list action")
        async with self.lock:
            values = self.read_list(kind)
            if body["action"] == "add" and identifier not in values:
                values.append(identifier)
            elif body["action"] == "remove":
                values = [value for value in values if value != identifier]
            path = self.data / ("banned-players.json" if kind == "bans" else "whitelist.txt")
            atomic_write(path, json.dumps(values) + "\n" if kind == "bans" else "\n".join(values) + "\n")
            if self.status == "Running":
                if kind == "whitelist":
                    valid = []
                    for value in values:
                        with contextlib.suppress(ValueError):
                            valid.append(str(uuid.UUID(value)))
                    await self.native("POST", "/whitelist", valid)
                elif body["action"] == "add":
                    with contextlib.suppress(web.HTTPException):
                        await self.native("POST", f"/players/{identifier}/kick", {"reason": "You have been banned from this server."})
            self.add_log(f"Dashboard {kind}: {body['action']} {identifier}")
        return await self.lists(request)

    async def history(self, request):
        hours = {"1h": 1, "6h": 6, "24h": 24}.get(request.query.get("range", "1h"))
        if not hours:
            raise ValueError("Invalid history range")
        step = hours * 5
        rows = self.db.execute("SELECT (time / ?) * ?, AVG(tps), AVG(mspt) FROM metrics WHERE time >= ? GROUP BY time / ? ORDER BY time",
                              (step, step, int(time.time())-hours*3600, step)).fetchall()
        return web.json_response([{"time": row[0]*1000, "tps": row[1], "mspt": row[2]} for row in rows])

    async def download_logs(self, request):
        return web.Response(text="\n".join(line["message"] for line in self.logs), content_type="text/plain",
                            headers={"Content-Disposition": 'attachment; filename="ferrumc-console.log"'})

    async def health(self, request):
        healthy = self.status in ("Stopped", "Stopping") or (
            self.status == "Starting" and time.monotonic()-self.started_at < 120) or (
            self.status == "Running" and time.monotonic()-self.last_metric < 15)
        return web.json_response({"healthy": healthy}, status=200 if healthy else 503)

    async def asset(self, request):
        relative = request.match_info.get("path", "")
        path = (self.static / relative).resolve()
        if not path.is_relative_to(self.static):
            raise web.HTTPNotFound()
        if path.is_dir():
            path = path / "index.html"
        if not path.is_file():
            if relative in ("console", "players", "config"):
                path = self.static / (relative + ".html")
            if not path.is_file():
                raise web.HTTPNotFound()
        return web.FileResponse(path)

    async def shutdown(self, app):
        self.closing = True
        await asyncio.gather(*(client.close() for client in list(self.clients)))

    async def lifecycle(self, app):
        self.http = ClientSession(timeout=ClientTimeout(total=5))
        self.tasks.append(asyncio.create_task(self.collect()))
        await self.start()
        yield
        self.closing = True
        for client in list(self.clients):
            await client.close()
        async with self.lock:
            await self.stop()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.http.close()
        self.db.close()

    def application(self):
        app = web.Application(middlewares=[self.security], client_max_size=65536)
        app.cleanup_ctx.append(self.lifecycle)
        app.on_shutdown.append(self.shutdown)
        app.add_routes([web.post("/api/login", self.login), web.post("/api/logout", self.logout),
            web.get("/api/session", self.session), web.get("/api/state", self.get_state),
            web.get("/api/config", self.get_config), web.put("/api/config", self.save_config),
            web.post("/api/power", self.power_action), web.post("/api/command", self.command),
            web.post("/api/players/{uuid}/kick", self.kick), web.get("/api/lists", self.lists),
            web.post("/api/lists/{kind}", self.change_list), web.get("/api/history", self.history),
            web.get("/api/logs/download", self.download_logs), web.get("/ws", self.websocket),
            web.get("/healthz", self.health), web.get("/{path:.*}", self.asset)])
        return app


def run(data, binary):
    manager = Manager(data, binary, os.environ.get("DASHBOARD_STATIC", "/opt/ferrumc/dashboard"),
                      int(os.environ.get("FERRUMC_BRIDGE_PORT", "9001")))
    web.run_app(manager.application(), host=os.environ.get("DASHBOARD_HOST", "0.0.0.0"),
                port=int(os.environ.get("DASHBOARD_PORT", "9000")), access_log=None, print=None,
                shutdown_timeout=115)

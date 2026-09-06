"""Authentication, request forgery prevention and configuration persistence."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import aiohttp
from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "docker"))
from manager import Manager

CONFIG = '''# Preserved user comment
motd = ["Test"]
max_players = 20
chunk_render_distance = 8
online_mode = true
whitelist = false
default_gamemode = "creative"
tps = 20
network_compression_threshold = 256
encryption_enabled = true
[database]
cache_size = 123
'''


class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name)
        (self.path / "configs").mkdir()
        (self.path / "configs/config.toml").write_text(CONFIG)
        with patch.dict(os.environ, {"DASHBOARD_PASSWORD": "test-password-for-ci"}):
            self.manager = Manager(self.path, "/unused", self.path)
        app = self.manager.application()
        app.cleanup_ctx.clear()  # Unit tests do not start a game server.
        self.client = TestClient(TestServer(app), cookie_jar=aiohttp.CookieJar(unsafe=True))
        await self.client.start_server()
        self.headers = {"X-FerrumC-Request": "dashboard"}

    async def asyncTearDown(self):
        await self.client.close()
        self.manager.db.close()
        self.directory.cleanup()

    async def login(self):
        response = await self.client.post("/api/login", json={"password": "test-password-for-ci"}, headers=self.headers)
        self.assertEqual(response.status, 200)
        self.assertTrue(response.cookies["ferrumc_session"]["httponly"])
        self.assertEqual(response.cookies["ferrumc_session"]["samesite"], "Strict")

    async def test_authentication_and_csrf(self):
        self.assertEqual((await self.client.get("/api/state")).status, 401)
        self.assertEqual((await self.client.post("/api/login", json={})).status, 403)
        self.assertEqual((await self.client.post("/api/login", json={"password": "wrong"}, headers=self.headers)).status, 401)
        await self.login()
        self.assertEqual((await self.client.get("/api/state")).status, 200)
        response = await self.client.post("/api/power", json={"action": "start"},
            headers=dict(self.headers, Origin="https://attacker.example"))
        self.assertEqual(response.status, 403)
        await self.client.post("/api/logout", json={}, headers=self.headers)
        self.assertEqual((await self.client.get("/api/state")).status, 401)

    async def test_websocket_origin_and_session(self):
        await self.login()
        with self.assertRaises(aiohttp.WSServerHandshakeError) as rejected:
            await self.client.ws_connect("/ws", origin="https://attacker.example")
        self.assertEqual(rejected.exception.status, 403)
        origin = str(self.client.make_url("/")).rstrip("/")
        async with self.client.ws_connect("/ws", origin=origin) as socket:
            self.assertEqual((await socket.receive_json())["type"], "State")
            self.manager.sessions.clear()
            message = await socket.receive(timeout=3)
            self.assertEqual(message.type, aiohttp.WSMsgType.CLOSE)
        with self.assertRaises(aiohttp.WSServerHandshakeError) as rejected:
            await self.client.ws_connect("/ws", origin=origin)
        self.assertEqual(rejected.exception.status, 401)

    async def test_config_conflicts_and_atomic_save(self):
        await self.login()
        original = await (await self.client.get("/api/config")).json()
        values = dict(original["values"], max_players=42, motd=['A "quoted" message'])
        response = await self.client.put("/api/config", json={"values": values, "revision": original["revision"]}, headers=self.headers)
        self.assertEqual(response.status, 200)
        self.assertTrue((await response.json())["managed"])
        self.assertEqual((self.path / "configs/config.toml.bak").read_text(), CONFIG)
        saved = (self.path / "configs/config.toml").read_text()
        self.assertIn("# Preserved user comment", saved)
        self.assertIn("cache_size = 123", saved)
        conflict = await self.client.put("/api/config", json={"values": values, "revision": original["revision"]}, headers=self.headers)
        self.assertEqual(conflict.status, 409)
        invalid = await self.client.put("/api/config", json={"values": dict(values, online_mode="false"), "revision": original["revision"]}, headers=self.headers)
        self.assertEqual(invalid.status, 400)
        self.assertEqual((self.path / "configs/config.toml").read_text(), saved)

    async def test_rate_limit_and_startup_health(self):
        for _ in range(8):
            self.assertEqual((await self.client.post("/api/login", json={"password": "wrong"}, headers=self.headers)).status, 401)
        self.assertEqual((await self.client.post("/api/login", json={"password": "wrong"}, headers=self.headers)).status, 429)
        self.manager.status = "Starting"
        self.manager.started_at = time.monotonic() - 121
        self.assertEqual((await self.client.get("/healthz")).status, 503)
        self.manager.status = "Stopped"
        self.assertEqual((await self.client.get("/healthz")).status, 200)

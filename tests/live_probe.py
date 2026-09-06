"""Protocol-level checks against the real release, using only the stdlib."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import struct
import sys
import urllib.request
from urllib.parse import urljoin


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "docker"))
from minecraft_status import read_exact, server_status


def probe(mc_port, dashboard_port):
    status = server_status(mc_port, timeout=10)
    assert status["version"]["protocol"] == 772, status
    assert status["players"]["online"] == 0, status
    url = f"http://127.0.0.1:{dashboard_port}"
    with urllib.request.urlopen(url, timeout=10) as response:
        html = response.read().decode()
        assert response.status == 200 and "_app/immutable/" in html
    for path in re.findall(r'href="(\./_app/[^\"]+\.js)"', html):
        with urllib.request.urlopen(urljoin(url + "/", path), timeout=10) as response:
            assert response.status == 200 and response.read(1)
    with socket.create_connection(("127.0.0.1", dashboard_port), timeout=10) as sock:
        key = base64.b64encode(os.urandom(16)).decode()
        request = (f"GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{dashboard_port}\r\n"
                   f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                   "Sec-WebSocket-Version: 13\r\n\r\n")
        sock.sendall(request.encode())
        stream = sock.makefile("rb")
        assert b"101" in stream.readline()
        headers = {}
        while (line := stream.readline()) != b"\r\n":
            if not line:
                raise EOFError("Incomplete WebSocket handshake")
            name, value = line.decode().split(":", 1)
            headers[name.lower()] = value.strip()
        expected = base64.b64encode(hashlib.sha1(
            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        assert headers["sec-websocket-accept"] == expected
        for expected_event in ("Handshake", "Metric"):
            first, second = read_exact(stream, 2)
            assert first == 0x81 and not second & 0x80
            size = second & 127
            if size == 126:
                size = struct.unpack(">H", read_exact(stream, 2))[0]
            elif size == 127:
                size = struct.unpack(">Q", read_exact(stream, 8))[0]
            assert size < 1048576
            event = json.loads(read_exact(stream, size))
            assert event["type"] == expected_event, event
            if expected_event == "Metric":
                assert event["data"]["ram_usage"] > 0
    print("PASS: Minecraft 1.21.8 status, dashboard HTML/JS and live WebSocket metrics")
    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mc-port", type=int, default=25565)
    parser.add_argument("--dashboard-port", type=int, default=9000)
    args = parser.parse_args()
    probe(args.mc_port, args.dashboard_port)

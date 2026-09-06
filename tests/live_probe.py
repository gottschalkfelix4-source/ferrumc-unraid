"""Protocol-level checks against the real release, using only the stdlib."""
import argparse
import base64
import hashlib
import json
import os
import re
import socket
import struct
import urllib.request
from urllib.parse import urljoin


def read_exact(stream, length):
    data = bytearray()
    while len(data) < length:
        part = stream.read(length - len(data))
        if not part:
            raise EOFError("Connection closed before the complete packet arrived")
        data.extend(part)
    return bytes(data)


def varint(number):
    result = bytearray()
    while number > 127:
        result.append((number & 127) | 128)
        number >>= 7
    result.append(number)
    return bytes(result)


def read_varint(stream):
    number = 0
    for offset in range(5):
        byte = read_exact(stream, 1)[0]
        number |= (byte & 127) << (7 * offset)
        if not byte & 128:
            return number
    raise ValueError("Invalid VarInt")


def probe(mc_port, dashboard_port):
    with socket.create_connection(("127.0.0.1", mc_port), timeout=10) as sock:
        stream = sock.makefile("rb")
        host = b"localhost"
        handshake = b"\x00" + varint(772) + varint(len(host)) + host + struct.pack(">H", mc_port) + b"\x01"
        sock.sendall(varint(len(handshake)) + handshake + b"\x01\x00")
        assert 0 < read_varint(stream) < 1048576
        assert read_varint(stream) == 0
        size = read_varint(stream)
        assert size < 1048576
        status = json.loads(read_exact(stream, size))
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

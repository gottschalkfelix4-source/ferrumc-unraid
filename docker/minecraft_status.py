"""Complete a Minecraft server-list status and ping/pong exchange."""
import json
import socket
import struct


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


def server_status(port=25565, timeout=2):
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        stream = sock.makefile("rb")
        host = b"localhost"
        handshake = b"\x00" + varint(772) + varint(len(host)) + host + struct.pack(">H", port) + b"\x01"
        sock.sendall(varint(len(handshake)) + handshake + b"\x01\x00")
        if not 0 < read_varint(stream) < 1048576 or read_varint(stream) != 0:
            raise ValueError("Invalid Minecraft status response")
        size = read_varint(stream)
        if not 0 < size < 1048576:
            raise ValueError("Invalid Minecraft status JSON size")
        status = json.loads(read_exact(stream, size))
        # A plain TCP probe or early disconnect makes FerrumC log a handshake error.
        payload = b"ferrumc!"
        sock.sendall(b"\x09\x01" + payload)
        if read_varint(stream) != 9 or read_exact(stream, 9) != b"\x01" + payload:
            raise ValueError("Invalid Minecraft pong response")
        return status


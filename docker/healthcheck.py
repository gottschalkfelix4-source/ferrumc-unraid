"""Check both Minecraft and the bundled dashboard, including missing UI assets."""
import socket
import urllib.request

with socket.create_connection(("127.0.0.1", 25565), timeout=2):
    pass
with urllib.request.urlopen("http://127.0.0.1:9000/", timeout=2) as response:
    html = response.read(65536)
    if response.status != 200 or b"_app/immutable/" not in html:
        raise SystemExit("FerrumC dashboard assets are unavailable")


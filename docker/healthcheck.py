"""Check both Minecraft and the bundled dashboard, including missing UI assets."""
import urllib.request
from minecraft_status import server_status

status = server_status()
if status["version"]["protocol"] != 772:
    raise SystemExit("Unexpected Minecraft protocol")
with urllib.request.urlopen("http://127.0.0.1:9000/", timeout=2) as response:
    html = response.read(65536)
    if response.status != 200 or b"_app/immutable/" not in html:
        raise SystemExit("FerrumC dashboard assets are unavailable")

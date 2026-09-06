"""The dashboard remains healthy when Minecraft is intentionally stopped."""
import json
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:9000/healthz", timeout=2) as response:
    assert json.load(response)["healthy"]
with urllib.request.urlopen("http://127.0.0.1:9000/", timeout=2) as response:
    assert b"_app/immutable/" in response.read(65536), "Dashboard assets missing"

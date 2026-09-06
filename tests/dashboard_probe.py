"""Exercise real dashboard/server actions; usable locally and against the image."""
import http.cookiejar
import json
import time
import urllib.error
import urllib.request
import uuid


class Dashboard:
    def __init__(self, port, password):
        self.url = f"http://127.0.0.1:{port}"
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.request("/login", "POST", {"password": password})

    def request(self, path, method="GET", data=None, expected=200):
        request = urllib.request.Request(self.url + "/api" + path,
            data=json.dumps(data).encode() if data is not None else None, method=method,
            headers={"Content-Type": "application/json", "X-FerrumC-Request": "dashboard"})
        try:
            response = self.opener.open(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            result = response.read()
            assert response.status == expected, (path, response.status, result)
            return json.loads(result) if "json" in response.headers.get("Content-Type", "") else result.decode()

    def wait(self, predicate, timeout=60):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.request("/state")
            if predicate(state):
                return state
            time.sleep(.5)
        raise TimeoutError(state)

    def power(self, action):
        self.request("/power", "POST", {"action": action}, expected=202)
        if action == "stop":
            return self.wait(lambda state: state["status"] == "Stopped" and not state["operation"])
        return self.wait(lambda state: state["fresh"] and not state["operation"])


def exercise(port, password):
    api = Dashboard(port, password)
    state = api.wait(lambda state: state["fresh"])
    assert state["metrics"]["ram_usage"] > 0
    assert 0 < state["metrics"]["tps"] <= 100
    token = uuid.uuid4().hex
    api.request("/command", "POST", {"command": "echo " + token})
    for _ in range(40):
        logs = api.request("/logs/download")
        if any("Server said" in line and token in line for line in logs.splitlines()):
            break
        time.sleep(.25)
    else:
        raise AssertionError("Command was not executed inside the native ECS")
    api.request("/command", "POST", {"command": "no_such_command"}, expected=400)
    api.request("/command", "POST", {"command": "echo \u00e4"}, expected=400)
    before = api.request("/config")
    body = {"values": dict(before["values"], max_players=21 if before["values"]["max_players"] != 21 else 22), "revision": before["revision"]}
    api.request("/config", "PUT", body)
    api.request("/config", "PUT", body, expected=409)
    current = api.request("/config")
    api.request("/config", "PUT", {"values": dict(current["values"], tps=0), "revision": current["revision"]}, expected=400)
    state = api.power("restart")
    assert state["config"]["max_players"] == body["values"]["max_players"] and not state["pending_config"], state
    for kind in ("bans", "whitelist"):
        api.request("/lists/" + kind, "POST", {"action": "add", "uuid": token})
        assert str(uuid.UUID(token)) in api.request("/lists")[kind]
    api.power("stop")
    with urllib.request.urlopen(api.url + "/healthz") as response:
        assert json.load(response)["healthy"]
    with urllib.request.urlopen(api.url + "/") as response:
        assert b"_app/immutable/" in response.read()
    api.power("start")
    for kind in ("bans", "whitelist"):
        assert str(uuid.UUID(token)) in api.request("/lists")[kind]
        api.request("/lists/" + kind, "POST", {"action": "remove", "uuid": token})
    assert api.request("/history?range=24h")
    api.request("/logout", "POST", {})
    api.request("/state", expected=401)
    print("PASS: native commands, config/revision validation, restart, stop/start, lists, metrics and logout")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    exercise(args.port, args.password)

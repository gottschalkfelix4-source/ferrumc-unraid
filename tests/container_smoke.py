"""Run a real container, then recreate it and verify persistent data and shutdown."""
import json
import subprocess
import sys
import time
import uuid

from live_probe import probe
from dashboard_probe import exercise


def docker(*args, check=True):
    result = subprocess.run(["docker", *args], text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=check)
    return result.stdout.strip()


def main(image):
    name = "ferrumc-test-" + uuid.uuid4().hex[:12]
    volume = name + "-data"
    password = "ferrumc-ci-" + uuid.uuid4().hex
    docker("volume", "create", volume)
    try:
        for iteration in range(2):
            docker("run", "-d", "--name", name, "--stop-timeout", "120",
                   "-p", "127.0.0.1::25565", "-p", "127.0.0.1::9000",
                   "-v", f"{volume}:/data", "-e", "PUID=99", "-e", "PGID=100",
                   "-e", "MAX_PLAYERS=20", "-e", "DASHBOARD_PASSWORD=" + password, "-e", 'MOTD=Test "persistent" world', image)
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                state = json.loads(docker("inspect", name))[0]["State"]
                if not state["Running"]:
                    raise RuntimeError("Container exited during startup")
                if state["Health"]["Status"] == "healthy":
                    break
                time.sleep(2)
            else:
                raise TimeoutError("Container did not become healthy")
            inspection = json.loads(docker("inspect", name))[0]
            ports = inspection["NetworkSettings"]["Ports"]
            status = probe(int(ports["25565/tcp"][0]["HostPort"]),
                           int(ports["9000/tcp"][0]["HostPort"]), password)
            assert status["players"]["max"] == (20 if iteration == 0 else 21)
            if iteration == 0:
                dashboard_port = int(ports["9000/tcp"][0]["HostPort"])
                minecraft_port = int(ports["25565/tcp"][0]["HostPort"])
                exercise(dashboard_port, password)
                subprocess.run(["node", "tests/client/players.cjs", str(dashboard_port), str(minecraft_port), password], check=True, timeout=240)
            script = '''import hashlib,json,pathlib,tomllib
p=pathlib.Path('/data')
c=tomllib.loads((p/'configs/config.toml').read_text())
assert c['motd']==['Test "persistent" world']
assert (p/'world').is_dir()
assert (p/'configs/config.toml').stat().st_uid==99
status=pathlib.Path('/proc/1/status').read_text()
assert 'Uid:\\t99\\t99\\t99\\t99' in status
print(hashlib.sha256((p/'configs/config.toml').read_bytes()).hexdigest())
'''
            checksum = docker("exec", name, "python", "-c", script)
            if iteration == 0:
                first_checksum = checksum
                docker("exec", "--user", "99:100", name, "python", "-c",
                       "from pathlib import Path; Path('/data/world/persistence-marker').write_text('retained')")
            else:
                assert checksum == first_checksum
                assert docker("exec", name, "cat", "/data/world/persistence-marker") == "retained"
            docker("stop", name)
            state = json.loads(docker("inspect", name))[0]["State"]
            assert state["ExitCode"] == 0, state
            logs = docker("logs", name)
            assert "Shutting down server" in logs and "Server exited successfully" in logs, logs
            assert "Unhandled handshake error" not in logs, logs
            docker("rm", name)
        print("PASS: non-root UID, environment config, world persistence, recreation and graceful shutdown")
    finally:
        # Logs aid diagnosing a failed image without leaving test containers around.
        result = subprocess.run(["docker", "logs", name], capture_output=True, text=True)
        if result.returncode == 0:
            print(result.stdout[-8000:], result.stderr[-2000:])
        docker("rm", "-f", name, check=False)
        docker("volume", "rm", volume, check=False)


if __name__ == "__main__":
    main(sys.argv[1])

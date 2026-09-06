"""Prepare persistent FerrumC data, drop privileges, then run the dashboard supervisor."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import tomlkit

DATA = Path(os.environ.get("FERRUMC_DATA", "/data"))
BINARY = Path(os.environ.get("FERRUMC_BINARY", "/opt/ferrumc/ferrumc"))


def integer(value, name, minimum, maximum):
    try:
        number = int(value)
    except ValueError:
        raise ValueError(f"{name} must be an integer") from None
    if not minimum <= number <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return number


def boolean(value, name):
    if value.lower() not in ("true", "false"):
        raise ValueError(f"{name} must be true or false")
    return value.lower() == "true"


def configure(text, env):
    """Only explicit environment values override the comment-preserving TOML."""
    config = tomlkit.parse(text)
    # Internal ports are fixed; Unraid/Compose remaps the host ports.
    config["host"] = "0.0.0.0"
    config["port"] = 25565
    config.setdefault("dashboard", tomlkit.table())["port"] = 9000
    for name, key, low, high in (
        ("MAX_PLAYERS", "max_players", 1, 10000),
        ("VIEW_DISTANCE", "chunk_render_distance", 2, 32),
        ("TPS", "tps", 1, 100),
    ):
        if env.get(name, "") != "":
            config[key] = integer(env[name], name, low, high)
    for name, key in (("ONLINE_MODE", "online_mode"), ("WHITELIST", "whitelist")):
        if env.get(name, "") != "":
            config[key] = boolean(env[name], name)
    if env.get("MOTD", "") != "":
        config["motd"] = [env["MOTD"]]
    if env.get("GAMEMODE", "") != "":
        if env["GAMEMODE"] not in ("creative", "survival", "adventure", "spectator"):
            raise ValueError("GAMEMODE must be creative, survival, adventure or spectator")
        config["default_gamemode"] = env["GAMEMODE"]
    return tomlkit.dumps(config)


def atomic_write(path, text):
    """Never truncate a working config if validation or writing fails."""
    fd, name = tempfile.mkstemp(prefix=".config-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(name, 0o660 & ~int(os.environ.get("UMASK", "002"), 8))
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def main():
    uid = integer(os.environ.get("PUID", "99"), "PUID", 1, 2147483647)
    gid = integer(os.environ.get("PGID", "100"), "PGID", 1, 2147483647)
    mask = int(os.environ.get("UMASK", "002"), 8)
    if not 0 <= mask <= 0o777:
        raise ValueError("UMASK must be an octal permission mask between 000 and 777")
    os.umask(mask)
    level = os.environ.get("LOG_LEVEL", "info")
    if level not in ("trace", "debug", "info", "warn", "error"):
        raise ValueError("LOG_LEVEL must be trace, debug, info, warn or error")
    DATA.mkdir(parents=True, exist_ok=True)
    if os.geteuid() == 0:
        os.chown(DATA, uid, gid)
        os.setgroups([])
        os.setgid(gid)
        os.setuid(uid)
    os.chdir(DATA)
    destination = DATA / "ferrumc"
    # FerrumC locates configs/world relative to the real executable, not cwd.
    # Copy (do not symlink) the image's binary and replace it on each restart.
    fd, name = tempfile.mkstemp(prefix=".ferrumc-", dir=DATA)
    os.close(fd)
    try:
        shutil.copyfile(BINARY, name)
        os.chmod(name, 0o755)
        os.replace(name, destination)
    finally:
        Path(name).unlink(missing_ok=True)
    subprocess.run([str(destination), "setup"], check=True)
    path = DATA / "configs/config.toml"
    before = path.read_text()
    after = configure(before, {} if (DATA / ".dashboard-config-managed").exists() else os.environ)
    if before != after:
        atomic_write(path, after)
    arguments = sys.argv[1:] or ["run"]
    print(f"Starting FerrumC as UID {os.geteuid()}, GID {os.getegid()}", flush=True)
    if arguments == ["run"]:
        from manager import run
        run(DATA, destination)
        return
    os.execv(str(destination), [str(destination), "--log", level, *arguments])


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        # Do not print config contents: the upstream dashboard secret lives there.
        if isinstance(error, PermissionError):
            print("Startup failed: /data must be writable by PUID:PGID. "
                  "Fix ownership of existing appdata before starting.", file=sys.stderr)
        else:
            print(f"Startup failed: {error}", file=sys.stderr)
        sys.exit(1)

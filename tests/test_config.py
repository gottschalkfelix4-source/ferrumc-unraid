import importlib.util
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location("entrypoint", Path(__file__).resolve().parents[1] / "docker/entrypoint.py")
entrypoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entrypoint)

CONFIG = '''# Keep my hand-written settings
host = "127.0.0.1"
port = 25565
motd = ["Custom world"]
max_players = 42
online_mode = true
[database]
db_path = "custom-world"
map_size = 77
[dashboard]
port = 9000
secret = "keep-this-secret"
'''


class ConfigTests(unittest.TestCase):
    def test_manual_settings_and_comments_survive(self):
        result = entrypoint.configure(CONFIG, {})
        config = tomllib.loads(result)
        self.assertIn("# Keep my hand-written settings", result)
        self.assertEqual(config["max_players"], 42)
        self.assertEqual(config["database"]["db_path"], "custom-world")
        self.assertEqual(config["dashboard"]["secret"], "keep-this-secret")
        self.assertEqual(config["host"], "0.0.0.0")

    def test_motd_cannot_inject_toml(self):
        motd = 'Hello "world"\nport = 1234\n[other]'
        config = tomllib.loads(entrypoint.configure(CONFIG, {"MOTD": motd}))
        self.assertEqual(config["motd"], [motd])
        self.assertEqual(config["port"], 25565)
        self.assertNotIn("other", config)

    def test_invalid_settings_rejected(self):
        for env in ({"ONLINE_MODE": "maybe"}, {"VIEW_DISTANCE": "999"},
                    {"MAX_PLAYERS": "-1"}, {"GAMEMODE": "typo"}, {"TPS": "abc"}):
            with self.subTest(env=env), self.assertRaises(ValueError):
                entrypoint.configure(CONFIG, env)

    def test_failed_atomic_replace_keeps_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(CONFIG)
            with patch.object(entrypoint.os, "replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    entrypoint.atomic_write(path, "new")
            self.assertEqual(path.read_text(), CONFIG)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_unraid_defaults_are_valid_config(self):
        root = ET.parse(Path(__file__).resolve().parents[1] / "unraid/ferrumc.xml").getroot()
        env = {node.attrib["Target"]: node.text or "" for node in root.findall("Config")
               if node.attrib["Type"] == "Variable"}
        config = tomllib.loads(entrypoint.configure(CONFIG, env))
        self.assertTrue(config["online_mode"])
        self.assertEqual(config["max_players"], 20)
        self.assertEqual(config["dashboard"]["port"], 9000)


if __name__ == "__main__":
    unittest.main()


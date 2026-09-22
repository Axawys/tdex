import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tdex import system
from tdex.catalog import parse_tool
from tdex.ui.dialogs import parse_args


def tool(**overrides):
    raw = {"name": "demo", "command": "demo-cmd", "mode": "user", "category": "Тест",
           "description": "d", "install": {"arch": "sudo pacman -S demo"}}
    raw.update(overrides)
    return parse_tool(raw, "test", 0)


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.env = mock.patch.dict(os.environ, {"PATH": self.dir.name})
        self.env.start()
        self.addCleanup(self.env.stop)

    def make_exe(self, name, mode=0o755):
        path = Path(self.dir.name) / name
        path.write_text("#!/bin/sh\n")
        path.chmod(mode)
        return str(path)

    def test_missing(self):
        self.assertIsNone(system.resolve(tool()))
        self.assertEqual(system.check(tool()).kind, system.MISSING)

    def test_found_in_path(self):
        path = self.make_exe("demo-cmd")
        self.assertEqual(system.resolve(tool()), system.Resolution("demo-cmd", path))

    def test_not_executable_is_missing(self):
        self.make_exe("demo-cmd", mode=0o644)
        self.assertIsNone(system.resolve(tool()))

    def test_alias_used_when_command_absent(self):
        path = self.make_exe("batcat")
        found = system.resolve(tool(command="bat", aliases=["batcat"]))
        self.assertEqual(found, system.Resolution("batcat", path))

    def test_builtin_status(self):
        self.assertEqual(system.check(tool(builtin=True)).kind, system.BUILTIN)

    def test_status_is_dynamic(self):
        cache = system.StatusCache()
        demo = tool()
        cache.scan([demo])
        self.assertFalse(cache.get(demo).available)
        self.make_exe("demo-cmd")
        cache.scan([demo])
        self.assertTrue(cache.get(demo).available)


class DistroTest(unittest.TestCase):
    def detect(self, text):
        with tempfile.NamedTemporaryFile("w", delete=False) as fh:
            fh.write(text)
        self.addCleanup(Path(fh.name).unlink)
        return system.detect_family(fh.name)

    def test_families(self):
        self.assertEqual(self.detect('ID=arch\n'), "arch")
        self.assertEqual(self.detect('ID=ubuntu\nID_LIKE=debian\n'), "debian")
        self.assertEqual(self.detect('ID="linuxmint"\nID_LIKE="ubuntu debian"\n'), "debian")
        self.assertEqual(self.detect('ID=fedora\n'), "fedora")
        self.assertEqual(self.detect('ID=rocky\nID_LIKE="rhel centos fedora"\n'), "fedora")
        self.assertIsNone(self.detect('ID=gentoo\n'))

    def test_missing_file(self):
        self.assertIsNone(system.detect_family("/nonexistent/os-release"))

    def test_aur_belongs_to_arch(self):
        self.assertTrue(system.key_matches_family("aur", "arch"))
        self.assertFalse(system.key_matches_family("aur", "debian"))


class ParseArgsTest(unittest.TestCase):
    def test_quotes_without_shell(self):
        self.assertEqual(parse_args('-n "a b" \'$HOME\' ; rm'), ["-n", "a b", "$HOME", ";", "rm"])

    def test_tilde_expansion(self):
        self.assertEqual(parse_args("~/x ~"), [os.path.expanduser("~/x"), os.path.expanduser("~")])

    def test_unbalanced_quote(self):
        with self.assertRaises(ValueError):
            parse_args('"open')


if __name__ == "__main__":
    unittest.main()

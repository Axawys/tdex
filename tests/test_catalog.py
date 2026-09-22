import json
import tempfile
import unittest
from pathlib import Path

from tdex.catalog import MODES, Catalog, CatalogError, builtin_catalog_path, load_file, parse_tool


def entry(**overrides):
    data = {
        "name": "btop",
        "command": "btop",
        "mode": "user",
        "category": "Мониторинг",
        "description": "Интерактивный мониторинг",
        "install": {"arch": "sudo pacman -S btop"},
    }
    data.update(overrides)
    return data


class ParseToolTest(unittest.TestCase):
    def test_minimal_entry(self):
        tool = parse_tool(entry(), "test", 0)
        self.assertEqual(tool.key, ("user", "btop"))
        self.assertFalse(tool.pause)
        self.assertFalse(tool.prompt_args)

    def test_system_defaults_to_prompt_and_pause(self):
        tool = parse_tool(entry(mode="system"), "test", 0)
        self.assertTrue(tool.pause)
        self.assertTrue(tool.prompt_args)

    def test_missing_field(self):
        raw = entry()
        del raw["install"]
        with self.assertRaisesRegex(CatalogError, "install"):
            parse_tool(raw, "test", 0)

    def test_invalid_mode(self):
        with self.assertRaisesRegex(CatalogError, "режим"):
            parse_tool(entry(mode="admin"), "test", 0)

    def test_command_with_arguments_rejected(self):
        for command in ("fortune | cowsay", "ls -la", "rm;reboot", "$(id)"):
            with self.subTest(command=command), self.assertRaises(CatalogError):
                parse_tool(entry(command=command), "test", 0)

    def test_args_must_be_string_list(self):
        with self.assertRaises(CatalogError):
            parse_tool(entry(args="-la"), "test", 0)

    def test_builtin_may_have_no_install(self):
        tool = parse_tool(entry(builtin=True, install={}), "test", 0)
        self.assertTrue(tool.builtin)
        with self.assertRaises(CatalogError):
            parse_tool(entry(install={}), "test", 0)


class LoadTest(unittest.TestCase):
    def write(self, data):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        with tmp:
            if isinstance(data, str):
                tmp.write(data)
            else:
                json.dump(data, tmp, ensure_ascii=False)
        self.addCleanup(Path(tmp.name).unlink)
        return tmp.name

    def test_accepts_list_and_object(self):
        self.assertEqual(len(load_file(self.write([entry()]))), 1)
        self.assertEqual(len(load_file(self.write({"tools": [entry()]}))), 1)

    def test_json_error_reports_line(self):
        with self.assertRaisesRegex(CatalogError, "строке 1"):
            load_file(self.write("{oops"))

    def test_later_file_overrides_same_key(self):
        first = self.write([entry(), entry(name="htop", command="htop")])
        second = self.write([entry(description="Переопределено")])
        catalog = Catalog.load([first, second])
        self.assertEqual([t.name for t in catalog.tools], ["btop", "htop"])
        self.assertEqual(catalog.tools[0].description, "Переопределено")


class BuiltinCatalogTest(unittest.TestCase):
    """Встроенный каталог должен загружаться и покрывать оба режима."""

    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog.load([builtin_catalog_path()])

    def test_both_modes_present(self):
        for mode in MODES:
            self.assertTrue(self.catalog.categories(mode), mode)

    def test_every_tool_explains_installation(self):
        for tool in self.catalog.tools:
            self.assertTrue(tool.install or tool.builtin, tool.name)

    def test_required_examples_present(self):
        names = {t.key for t in self.catalog.tools}
        for key in [("user", "btop"), ("user", "lazygit"), ("user", "2048"),
                    ("system", "grep"), ("system", "systemctl"), ("system", "timeout")]:
            self.assertIn(key, names)


class SearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog.load([builtin_catalog_path()])

    def names(self, mode, query):
        return [t.name for t in self.catalog.search(mode, query)]

    def test_monitor_finds_monitoring_tools(self):
        found = self.names("user", "monitor")
        for name in ("btop", "htop", "atop", "bottom"):
            self.assertIn(name, found)

    def test_search_is_limited_to_mode(self):
        self.assertIn("grep", self.names("system", "grep"))
        self.assertNotIn("grep", self.names("user", "grep"))
        self.assertNotIn("btop", self.names("system", "btop"))

    def test_name_match_ranks_first(self):
        self.assertEqual(self.names("user", "htop")[0], "htop")

    def test_russian_description_and_category(self):
        self.assertIn("vim", self.names("user", "редактор"))
        self.assertIn("tar", self.names("system", "архивы"))

    def test_yo_insensitive(self):
        self.assertEqual(self.names("user", "лёгкий"), self.names("user", "легкий"))

    def test_all_terms_must_match(self):
        self.assertEqual(self.names("user", "monitor gpu"), ["nvtop"])

    def test_empty_query(self):
        self.assertEqual(self.names("user", "   "), [])


if __name__ == "__main__":
    unittest.main()

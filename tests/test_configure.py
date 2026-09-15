import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("configure", ROOT / "configure.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class Desktop:
    def __init__(self):
        self.enabled = False
        self.calls = []
        self.config_checks = 0
        self.reject_config = False
        self.fail_enable = False

    def __call__(self, *args):
        self.calls.append(args)
        if args == ("hyprctl", "configerrors"):
            self.config_checks += 1
            return "bad native rule" if self.reject_config and self.config_checks == 2 else ""
        if args == ("omarchy-shell", "shell", "listPlugins"):
            return json.dumps([{"id": setup.PLUGIN_ID, "enabled": self.enabled}])
        if args[:3] == ("omarchy", "plugin", "enable"):
            if self.fail_enable:
                raise setup.SetupError("enable failed")
            self.enabled = True
        if args[:3] == ("omarchy", "plugin", "disable"):
            self.enabled = False
        return ""


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.plugin = self.home / ".config/omarchy/plugins" / setup.PLUGIN_ID
        self.plugin.mkdir(parents=True)
        self.config = self.home / ".config/hypr/hyprland.lua"
        self.config.parent.mkdir()
        self.original = '-- Personal settings\nrequire("default.hypr.omarchy")\nrequire("hypr.attention")\n'
        self.config.write_text(self.original)
        self.desktop = Desktop()

    def apply(self, action):
        return setup.configure(action, self.home, self.plugin, self.desktop)

    def test_install_twice_and_remove_preserves_unrelated_edits(self):
        backup = self.apply("install")
        self.assertEqual(backup.read_text(), self.original)
        self.assertTrue(self.desktop.enabled)
        self.assertEqual(self.config.read_text(), self.original + setup.BLOCK)
        self.assertIsNone(self.apply("install"))
        self.config.write_text(self.config.read_text() + '-- Added later\n')
        self.apply("remove")
        self.assertEqual(self.config.read_text(), self.original + '-- Added later\n')
        self.assertFalse(self.desktop.enabled)
        self.assertIsNone(self.apply("remove"))

    def test_rejected_native_rule_rolls_back_config_and_enablement(self):
        self.desktop.reject_config = True
        with self.assertRaisesRegex(setup.SetupError, "bad native rule"):
            self.apply("install")
        self.assertEqual(self.config.read_text(), self.original)
        self.assertFalse(self.desktop.enabled)
        self.assertEqual(self.desktop.config_checks, 3)

    def test_enable_failure_rolls_back_config(self):
        self.desktop.fail_enable = True
        with self.assertRaisesRegex(setup.SetupError, "enable failed"):
            self.apply("install")
        self.assertEqual(self.config.read_text(), self.original)
        self.assertFalse(self.desktop.enabled)

    def test_prior_enabled_state_survives_failed_install(self):
        self.desktop.enabled = True
        self.desktop.reject_config = True
        with self.assertRaises(setup.SetupError):
            self.apply("install")
        self.assertTrue(self.desktop.enabled)

    def test_edited_or_incomplete_managed_block_is_not_overwritten(self):
        for text in [setup.BLOCK.replace('do\n', 'do -- personal edit\n'), setup.BEGIN + '\n']:
            for action in ['install', 'remove']:
                self.config.write_text(self.original + text)
                with self.assertRaisesRegex(setup.SetupError, "edited or is incomplete"):
                    self.apply(action)
                self.assertEqual(self.config.read_text(), self.original + text)

    def test_original_manual_installation_is_not_duplicated(self):
        content = self.original + 'require("hypr.fullscreen-border")\n'
        self.config.write_text(content)
        with self.assertRaisesRegex(setup.SetupError, "already loaded"):
            self.apply("install")
        self.assertEqual(self.config.read_text(), content)

    def test_concurrent_edit_survives_failed_enable(self):
        desktop = self.desktop
        def racing_desktop(*args):
            if args[:3] == ('omarchy', 'plugin', 'enable'):
                self.config.write_text(self.config.read_text() + '-- concurrent change\n')
                raise setup.SetupError('enable failed')
            return desktop(*args)
        with self.assertRaisesRegex(setup.SetupError, "preserved it"):
            setup.configure('install', self.home, self.plugin, racing_desktop)
        self.assertTrue(self.config.read_text().endswith('-- concurrent change\n'))

    def test_wrong_install_location_does_not_edit_config(self):
        with self.assertRaisesRegex(setup.SetupError, "First install or extract"):
            setup.configure('install', self.home, ROOT, self.desktop)
        self.assertEqual(self.config.read_text(), self.original)

    def test_symlink_config_is_not_replaced(self):
        target = self.home / 'managed-config.lua'
        self.config.rename(target)
        self.config.symlink_to(target)
        with self.assertRaisesRegex(setup.SetupError, 'regular Omarchy Lua config'):
            self.apply('install')
        self.assertTrue(self.config.is_symlink())
        self.assertEqual(target.read_text(), self.original)


if __name__ == '__main__':
    unittest.main()

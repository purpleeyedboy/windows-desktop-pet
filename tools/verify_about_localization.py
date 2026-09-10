"""Focused, headless About acceptance checks; deliberately not the old pytest suite."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desktop_pet.foundation import about
from desktop_pet.foundation.config import BuildInfo, FeatureConfig
from desktop_pet.foundation.runtime import Activity, RuntimeSnapshot


class AboutChecks(unittest.TestCase):
    def test_windows_display_language_not_regional_format(self):
        for langid in (0x0804, 0x0404, 0x0C04, 0x1004, 0x1404):
            with self.subTest(langid=langid), patch.object(about.sys, "platform", "win32"), patch.object(about, "_windows_ui_language", return_value=langid):
                self.assertEqual(about.system_language(), "zh")
        with patch.object(about.sys, "platform", "win32"), patch.object(about, "_windows_ui_language", return_value=0x0411):
            self.assertEqual(about.system_language(), "en")

    def test_locale_fallback_and_failure(self):
        with patch.object(about.sys, "platform", "linux"):
            for locale_name, expected in (("zh_CN", "zh"), ("zh-Hant-TW", "zh"), ("en_US", "en"), (None, "en")):
                with patch.object(about.locale, "getlocale", return_value=(locale_name, "UTF-8")):
                    self.assertEqual(about.system_language(), expected)
        with patch.object(about.sys, "platform", "win32"), patch.object(about, "_windows_ui_language", side_effect=OSError):
            self.assertEqual(about.system_language(), "en")

    def test_all_fields_author_and_activity_translated_without_changing_identity(self):
        info = BuildInfo("2.1.0", date(2026, 9, 10), "abc123", "fullhash", FeatureConfig(test_build=True))
        original = info.as_fields()
        for activity in Activity:
            state = RuntimeSnapshot(activity=activity, activity_version=7)
            title, text = about.about_content(info, state, "zh")
            self.assertEqual(title, "关于 / 运行状态")
            self.assertIn("作者: Alex&Xixi", text)
            self.assertIn("测试版本: 是", text)
            self.assertIn("调试菜单: 否", text)
            self.assertIn("当前活动:", text)
            self.assertNotIn("当前活动: " + activity.value, text)
            self.assertIn("abc123", text)
        title, text = about.about_content(info, state, "en")
        self.assertEqual(title, "About / Runtime status")
        self.assertIn("Author: Alex&Xixi", text)
        self.assertTrue(text.isascii())
        self.assertEqual(info.as_fields(), original)

    def test_window_uses_presenter_and_parent(self):
        from desktop_pet.window import PetWindow
        window = PetWindow.__new__(PetWindow)
        window.root = object()
        window.services = SimpleNamespace(build_info=BuildInfo("2.1.0", date.today(), "source"), runtime=SimpleNamespace(snapshot=lambda: RuntimeSnapshot()))
        with patch("desktop_pet.window.about_content", return_value=("About", "Author: Alex&Xixi")), patch("desktop_pet.window.messagebox.showinfo") as show:
            window._show_about()
            show.assert_called_once_with("About", "Author: Alex&Xixi", parent=window.root)
        window._topmost_var = object()
        with patch("desktop_pet.window.about_title", return_value="About / Runtime status"), patch("desktop_pet.window.tk.Menu") as menu:
            window._create_menu()
            menu.return_value.add_command.assert_any_call(label="About / Runtime status", command=window._show_about)


if __name__ == "__main__":
    unittest.main()

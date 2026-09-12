"""Human-readable About presentation; build metadata remains machine-readable."""
import ctypes
import locale
import sys

from .config import BuildInfo
from .runtime import RuntimeSnapshot


def _windows_ui_language() -> int:
    # UI language, not the date/currency regional format or Python process locale.
    get_language = ctypes.WinDLL("kernel32", use_last_error=True).GetUserDefaultUILanguage
    get_language.argtypes = []
    get_language.restype = ctypes.c_ushort
    return get_language()


def system_language() -> str:
    try:
        if sys.platform == "win32":
            return "zh" if _windows_ui_language() & 0x3FF == 0x04 else "en"
        name = locale.getlocale()[0] or ""
        return "zh" if name.replace("_", "-").lower().split("-")[0] == "zh" else "en"
    except (OSError, AttributeError, ValueError):
        return "en"


def about_title(language: str | None = None) -> str:
    return "关于 / 运行状态" if (language or system_language()) == "zh" else "About / Runtime status"


_LABELS = {
    "product_version": ("产品版本", "Product version"),
    "build_date": ("构建日期", "Build date"),
    "git_short_hash": ("代码提交", "Git commit"),
    "foundation_commit": ("基础提交", "Foundation commit"),
    "foundation_label": ("基础版本", "Foundation version"),
    "enabled_features": ("启用功能", "Enabled features"),
    "test_build": ("测试版本", "Test build"),
    "debug_enabled": ("调试功能", "Debug enabled"),
    "debug_menu_enabled": ("调试菜单", "Debug menu"),
    "documentation_baseline": ("文档基线", "Documentation baseline"),
}
_ACTIVITIES = {
    "idle": "待机", "blink": "眨眼", "groom": "舔手梳理",
    "normal_hunger_animation": "轻度饥饿动画", "body_action": "身体互动",
    "severe_hunger_animation": "中度饥饿动画", "context_menu_open": "右键菜单",
    "drag_preview": "拖放期待", "transaction_review": "事务复核",
    "feed_confirm": "喂食确认", "feed_animation": "进食动画",
    "feed_processing": "文件处理", "shutting_down": "正在退出",
}
_FEATURES = {"common-foundation": "公共基础", "common-foundation-runtime": "公共基础运行时"}


def about_content(info: BuildInfo, state: RuntimeSnapshot, language: str | None = None) -> tuple[str, str]:
    language = language or system_language()
    chinese = language == "zh"
    rows = ["作者: Alex&Xixi" if chinese else "Author: Alex&Xixi"]
    for key, value in info.as_fields().items():
        label = _LABELS.get(key, (key, key))[0 if chinese else 1]
        if key in ("test_build", "debug_enabled", "debug_menu_enabled"):
            value = ("是" if value == "true" else "否") if chinese else ("Yes" if value == "true" else "No")
        elif chinese and key == "enabled_features":
            value = "、".join(_FEATURES.get(item, item) for item in value.split(","))
        elif chinese and value == "source":
            value = "源码运行（未打包）"
        rows.append(f"{label}: {value}")
    activity = state.activity.value
    rows.append(f"当前活动: {_ACTIVITIES.get(activity, activity)}" if chinese else f"Current activity: {activity.replace('_', ' ')}")
    rows.append(f"活动版本: {state.activity_version}" if chinese else f"Activity version: {state.activity_version}")
    return about_title(language), "\n".join(rows)

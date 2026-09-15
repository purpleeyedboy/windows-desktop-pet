"""Visible identity for test candidates and duplicate-instance notices."""

from __future__ import annotations

import json

from .paths import asset_path


def runtime_identity() -> str:
    path = asset_path("DRAG_EXPECTATION_BUILD_INFO.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "桌面宠物（开发源码；构建身份不可用）"
    features = ", ".join(data.get("enabled_features", ()))
    return "\n".join(
        (
            f"版本：{data.get('version', 'unknown')}",
            f"Git：{data.get('git_short_hash', 'unknown')}",
            f"基础：{data.get('foundation_commit', 'NOT-INTEGRATED')}",
            f"基线：{data.get('baseline', 'unknown')}",
            f"功能：{features}",
            f"测试标志：{data.get('automated_test_status', 'unknown')}",
            f"状态：{data.get('candidate_status', 'unknown')}",
        )
    )

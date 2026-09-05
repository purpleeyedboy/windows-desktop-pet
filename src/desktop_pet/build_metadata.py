"""Read the identity embedded in an independently built candidate."""

from __future__ import annotations

import json

from .paths import asset_path


SOURCE_FALLBACK = {
    "product_version": "2.1.1-test",
    "build_date": "source checkout",
    "git_short_hash": "not packaged",
    "baseline": "BASE-001",
    "enabled_features": ["既有基线", "双耳点击反馈"],
    "channel": "未自动测试；等待用户 Windows 实机验收的候选版",
    "documentation_baseline": "V2.1-EARS",
}


def load_build_metadata() -> dict[str, object]:
    path = asset_path("build-metadata.json")
    if not path.is_file():
        return dict(SOURCE_FALLBACK)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("build metadata must be an object")
    return value


def format_build_metadata() -> str:
    value = load_build_metadata()
    features = "、".join(str(item) for item in value["enabled_features"])
    return "\n".join(
        (
            f"产品版本：{value['product_version']}",
            f"构建日期：{value['build_date']}",
            f"Git：{value['git_short_hash']}",
            f"基础标签：{value['baseline']}",
            f"启用功能：{features}",
            f"渠道：{value['channel']}",
            f"文档基线：{value['documentation_baseline']}",
        )
    )

from desktop_pet.build_metadata import format_build_metadata, load_build_metadata


def test_source_metadata_identifies_baseline_features_beta_and_documentation() -> None:
    metadata = load_build_metadata()
    assert metadata["baseline"] == "BASE-001"
    assert metadata["enabled_features"] == ["既有基线", "双耳点击反馈"]
    assert metadata["channel"] == "未自动测试；等待用户 Windows 实机验收的候选版"
    assert metadata["documentation_baseline"] == "V2.1-EARS"
    text = format_build_metadata()
    for label in ("产品版本", "构建日期", "Git", "基础标签", "启用功能", "渠道", "文档基线"):
        assert f"{label}：" in text

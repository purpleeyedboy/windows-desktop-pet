from datetime import date

import pytest

from desktop_pet.foundation.config import BuildInfo, DebugInjectionDenied, FeatureConfig


def test_build_info_contains_required_foundation_identity():
    info = BuildInfo(
        product_version="2.1.0",
        build_date=date(2026, 9, 4),
        git_short_hash="c3b218d",
    )
    assert info.foundation_label == "V2.1-CORE"
    assert info.documentation_baseline == "BASE-001"
    assert info.as_fields()["enabled_features"] == "common-foundation"
    assert info.as_fields()["test_build"] == "false"
    assert info.as_fields()["debug_menu_enabled"] == "false"


def test_debug_injection_requires_test_build_or_explicit_debug_switch():
    with pytest.raises(DebugInjectionDenied):
        FeatureConfig().require_debug_injection()
    assert FeatureConfig(test_build=True).require_debug_injection() is None
    assert FeatureConfig(debug_enabled=True).require_debug_injection() is None
    assert FeatureConfig().enabled_features == ("common-foundation",)

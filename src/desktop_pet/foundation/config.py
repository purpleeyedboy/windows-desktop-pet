from dataclasses import dataclass, field
from datetime import date
from typing import ClassVar


class DebugInjectionDenied(PermissionError):
    pass


@dataclass(frozen=True)
class BuildInfo:
    product_version: str
    build_date: date
    git_short_hash: str
    feature_config: "FeatureConfig" = field(default_factory=lambda: FeatureConfig())
    foundation_label: ClassVar[str] = "V2.1-CORE"
    documentation_baseline: ClassVar[str] = "BASE-001"

    def as_fields(self) -> dict[str, str]:
        return {
            "product_version": self.product_version,
            "build_date": self.build_date.isoformat(),
            "git_short_hash": self.git_short_hash,
            "foundation_label": self.foundation_label,
            "enabled_features": ",".join(self.feature_config.enabled_features),
            "test_build": str(self.feature_config.test_build).lower(),
            "debug_enabled": str(self.feature_config.debug_enabled).lower(),
            "debug_menu_enabled": str(self.feature_config.debug_menu_enabled).lower(),
            "documentation_baseline": self.documentation_baseline,
        }


@dataclass(frozen=True)
class FeatureConfig:
    enabled_features: tuple[str, ...] = ("common-foundation",)
    test_build: bool = False
    debug_enabled: bool = False
    debug_menu_enabled: bool = False

    def __post_init__(self) -> None:
        if self.debug_menu_enabled and not (self.test_build or self.debug_enabled):
            raise DebugInjectionDenied("debug menu requires a test build or explicit debug switch")

    def require_debug_injection(self) -> None:
        if not (self.test_build or self.debug_enabled):
            raise DebugInjectionDenied("debug injection is disabled in production")

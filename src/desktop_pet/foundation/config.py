from dataclasses import dataclass, field
from datetime import date
import json
from pathlib import Path
import sys
from typing import ClassVar


class DebugInjectionDenied(PermissionError):
    pass


@dataclass(frozen=True)
class BuildInfo:
    product_version: str
    build_date: date
    git_short_hash: str
    foundation_commit: str = "source"
    feature_config: "FeatureConfig" = field(default_factory=lambda: FeatureConfig())
    foundation_label: ClassVar[str] = "V2.1-CORE"
    documentation_baseline: ClassVar[str] = "BASE-001"

    @classmethod
    def load_embedded(cls) -> "BuildInfo":
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
        path = root / "build_identity.json"
        if not path.is_file():
            return cls("2.1.0", date.today(), "source", "source", FeatureConfig(enabled_features=("common-foundation", "ears"), test_build=True, debug_enabled=True, debug_menu_enabled=True))
        payload = json.loads(path.read_text(encoding="utf-8"))
        features = FeatureConfig(
            enabled_features=tuple(payload["enabled_features"]),
            test_build=bool(payload["test_build"]),
            debug_enabled=bool(payload["debug_enabled"]),
            debug_menu_enabled=bool(payload["debug_menu_enabled"]),
        )
        return cls(payload["product_version"], date.fromisoformat(payload["build_date"]), payload["git_short_hash"], payload["foundation_commit"], features)

    def as_fields(self) -> dict[str, str]:
        return {
            "product_version": self.product_version,
            "build_date": self.build_date.isoformat(),
            "git_short_hash": self.git_short_hash,
            "foundation_commit": self.foundation_commit,
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

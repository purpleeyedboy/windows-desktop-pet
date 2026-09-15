from __future__ import annotations

import pytest

from desktop_pet.lick_compositor import GroomAssetsUnavailable
from tools.build_idle_lick_preview import build_preview


def test_preview_refuses_to_generate_placeholder_art_without_reviewed_assets(tmp_path) -> None:
    with pytest.raises(GroomAssetsUnavailable, match="missing grooming manifest"):
        build_preview(tmp_path / "missing-assets", tmp_path / "preview")

    assert not (tmp_path / "preview").exists()

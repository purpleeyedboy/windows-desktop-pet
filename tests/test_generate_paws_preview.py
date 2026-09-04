from pathlib import Path

from PIL import Image

from tools.generate_paws_preview import generate_preview


def test_preview_is_generated_only_at_requested_temporary_path(tmp_path):
    output = tmp_path / "paws-preview.png"
    generate_preview(output)
    with Image.open(output) as image:
        assert image.mode == "RGBA"
        assert image.size == (2048, 768)
    assert not Path("qa/v2.1-paws/paw-press-preview.png").exists()

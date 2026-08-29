from pathlib import Path

from PIL import Image, ImageDraw

from tools.rig_center_qa import ARTIFACTS, write_center_qa


def make_valid_center_source(root: Path) -> Path:
    source = root / "source"
    layers = source / "layers"
    masks = source / "masks"
    ai = source / "ai"
    sample = root / "samples" / "center"
    for directory in (layers, masks, ai, sample):
        directory.mkdir(parents=True)

    canonical = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    ImageDraw.Draw(canonical).rectangle(
        (80, 180, 239, 559), fill=(210, 140, 80, 255)
    )
    canonical.save(source / "canonical-idle.png")
    canonical.save(layers / "body_base.png")
    canonical.save(sample / "composite.png")
    for name in ("head_neck_base.png", "eye_left.png", "eye_right.png"):
        Image.new("RGBA", canonical.size, (0, 0, 0, 0)).save(layers / name)

    mask_specs = {
        "eye_left_mask.png": (110, 240, 130, 260),
        "eye_right_mask.png": (160, 240, 180, 260),
    }
    for name, box in mask_specs.items():
        mask = Image.new("L", canonical.size, 0)
        ImageDraw.Draw(mask).ellipse(box, fill=255)
        mask.save(layers / name)

    body_mask = Image.new("L", canonical.size, 0)
    ImageDraw.Draw(body_mask).rectangle((100, 365, 235, 550), fill=255)
    body_mask.save(masks / "body-fill-mask.png")
    eye_left = Image.open(layers / "eye_left_mask.png").convert("L")
    eye_right = Image.open(layers / "eye_right_mask.png").convert("L")
    eye_left.save(masks / "eye-left-mask.png")
    eye_right.save(masks / "eye-right-mask.png")
    Image.new("RGBA", canonical.size, (0, 0, 0, 0)).save(
        ai / "body-fill-raw.png"
    )
    Image.new("RGBA", canonical.size, (0, 0, 0, 0)).save(
        ai / "eye-fill-raw.png"
    )
    return source


def test_center_qa_writes_complete_exact_evidence(tmp_path: Path) -> None:
    source = make_valid_center_source(tmp_path)
    sample = source.parent / "samples" / "center"
    qa = tmp_path / "qa"

    report = write_center_qa(source, sample, qa)

    assert set(report["artifacts"]) == set(ARTIFACTS)
    assert report["exact_recomposition"] == {
        "matches": True,
        "changed_pixels": 0,
        "maximum_channel_delta": 0,
    }
    assert report["changed_pixels"] == 0
    assert report["maximum_channel_delta"] == 0
    assert report["alpha"]["alpha_zero_rgb_violations"] == 0
    assert report["alpha"]["outer_border_transparent"] is True
    assert report["alpha_zero_rgb_violations"] == 0
    assert set(report["layer_sha256"]) == {
        "body_base",
        "head_neck",
        "eye_left",
        "eye_right",
        "composite",
    }
    assert all(len(value) == 64 for value in report["layer_sha256"].values())
    assert report["mask_boxes"] == {
        "eye_left_mask.png": [110, 240, 131, 261],
        "eye_right_mask.png": [160, 240, 181, 261],
    }
    assert report["ai_containment"] == {
        "body_fill_outside_mask_pixels": 0,
        "eye_fill_outside_masks_pixels": 0,
        "passed": True,
    }
    assert all((qa / name).is_file() for name in ARTIFACTS)
    with Image.open(qa / "center-backgrounds.png") as image:
        assert image.mode == "RGB"

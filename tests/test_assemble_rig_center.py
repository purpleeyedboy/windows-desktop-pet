from pathlib import Path

from PIL import Image, ImageDraw

from tools.assemble_rig_center import assemble_center, normalize_fill


def test_normalize_fill_discards_generated_pixels_outside_mask() -> None:
    generated = Image.new("RGBA", (1024, 1536), (255, 0, 255, 255))
    mask = Image.new("L", (512, 768), 0)
    ImageDraw.Draw(mask).rectangle((100, 200, 140, 240), fill=255)
    result = normalize_fill(generated, mask)
    assert result.getpixel((0, 0)) == (0, 0, 0, 0)
    assert result.getpixel((120, 220)) == (255, 0, 255, 255)


def test_assemble_center_is_exact_and_keeps_ai_hidden(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "masks").mkdir(parents=True)
    (source / "ai").mkdir()
    canonical = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    ImageDraw.Draw(canonical).rectangle((80, 180, 260, 560), fill=(210, 140, 80, 255))
    canonical.save(source / "canonical-idle.png")
    dynamic = Image.new("L", canonical.size, 0)
    ImageDraw.Draw(dynamic).rectangle((80, 180, 220, 460), fill=255)
    body_fill = Image.new("L", canonical.size, 0)
    ImageDraw.Draw(body_fill).rectangle((100, 360, 200, 450), fill=255)
    left = Image.new("L", canonical.size, 0)
    right = Image.new("L", canonical.size, 0)
    ImageDraw.Draw(left).ellipse((110, 240, 130, 260), fill=255)
    ImageDraw.Draw(right).ellipse((160, 240, 180, 260), fill=255)
    for name, image in {
        "dynamic-head-neck-mask.png": dynamic,
        "body-fill-mask.png": body_fill,
        "eye-left-mask.png": left,
        "eye-right-mask.png": right,
    }.items():
        image.save(source / "masks" / name)
    Image.new("RGBA", canonical.size, (20, 30, 40, 255)).save(source / "ai" / "body-fill-raw.png")
    Image.new("RGBA", canonical.size, (50, 60, 70, 255)).save(source / "ai" / "eye-fill-raw.png")
    report = assemble_center(source, tmp_path / "samples" / "center")
    assert report["changed_pixels"] == 0
    assert report["maximum_channel_delta"] == 0


def test_assemble_center_is_exact_with_a_partially_transparent_eye_mask(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    (source / "masks").mkdir(parents=True)
    (source / "ai").mkdir()
    canonical = Image.new("RGBA", (512, 768), (210, 140, 80, 255))
    canonical.save(source / "canonical-idle.png")
    Image.new("L", canonical.size, 255).save(
        source / "masks" / "dynamic-head-neck-mask.png"
    )
    Image.new("L", canonical.size, 0).save(source / "masks" / "body-fill-mask.png")
    left = Image.new("L", canonical.size, 0)
    left.putpixel((110, 240), 128)
    left.save(source / "masks" / "eye-left-mask.png")
    Image.new("L", canonical.size, 0).save(source / "masks" / "eye-right-mask.png")
    Image.new("RGBA", canonical.size, (20, 30, 40, 255)).save(
        source / "ai" / "body-fill-raw.png"
    )
    Image.new("RGBA", canonical.size, (50, 60, 70, 255)).save(
        source / "ai" / "eye-fill-raw.png"
    )
    report = assemble_center(source, tmp_path / "samples" / "center")
    assert report["changed_pixels"] == 0
    assert report["maximum_channel_delta"] == 0


def test_assemble_center_preserves_transparent_canonical_edge_pixels(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    (source / "masks").mkdir(parents=True)
    (source / "ai").mkdir()
    canonical = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    canonical.putpixel((110, 240), (20, 30, 40, 254))
    canonical.save(source / "canonical-idle.png")
    Image.new("L", canonical.size, 255).save(
        source / "masks" / "dynamic-head-neck-mask.png"
    )
    body_fill = Image.new("L", canonical.size, 0)
    body_fill.putpixel((110, 240), 255)
    body_fill.save(source / "masks" / "body-fill-mask.png")
    for name in ("eye-left", "eye-right"):
        Image.new("L", canonical.size, 0).save(source / "masks" / f"{name}-mask.png")
    Image.new("RGBA", canonical.size, (20, 30, 40, 255)).save(
        source / "ai" / "body-fill-raw.png"
    )
    Image.new("RGBA", canonical.size, (50, 60, 70, 255)).save(
        source / "ai" / "eye-fill-raw.png"
    )
    report = assemble_center(source, tmp_path / "samples" / "center")
    assert report["changed_pixels"] == 0
    assert report["maximum_channel_delta"] == 0

from pathlib import Path

from PIL import Image, ImageDraw

import tools.process_ai_transitions as ai_transitions
from tools.process_ai_transitions import (
    FINAL_POSITIONS,
    INTERMEDIATE_COUNTS,
    assemble_action,
    extract_transition_cells,
    interpolate_bbox,
    render_transition_cell,
)


FRAME_SIZE = (512, 768)


def make_keyframe(path: Path, bbox: tuple[int, int, int, int], color: tuple[int, int, int]) -> None:
    image = Image.new("RGBA", FRAME_SIZE, (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle(bbox, fill=(*color, 255))
    image.save(path)


def make_transition_sheet(path: Path, occupied_cells: int) -> None:
    sheet = Image.new("RGB", (300, 200), (0, 0, 255))
    draw = ImageDraw.Draw(sheet)
    for index in range(occupied_cells):
        column = index % 3
        row = index // 3
        left = column * 100 + 25
        top = row * 100 + 15
        draw.rectangle((left, top, left + 49, top + 69), fill=(230, 160, 90))
    sheet.save(path)


def make_action_fixture(root: Path) -> tuple[Path, Path]:
    keyframes = root / "keys"
    sources = root / "sources"
    keyframes.mkdir()
    sources.mkdir()
    for index in range(6):
        make_keyframe(
            keyframes / f"{index:02d}.png",
            (80 + index * 8, 240 - index * 12, 300 + index * 6, 720 - index * 8),
            (220, 110 + index * 10, 45),
        )
    for segment, count in enumerate(INTERMEDIATE_COUNTS):
        make_transition_sheet(sources / f"segment_{segment:02d}_{segment + 1:02d}.png", count)
    return keyframes, sources


def test_extract_transition_cells_uses_reading_order_and_requested_count():
    sheet = Image.new("RGB", (300, 200), (0, 0, 255))
    for index in range(6):
        x = (index % 3) * 100 + 50
        y = (index // 3) * 100 + 50
        sheet.putpixel((x, y), (index + 1, 0, 0))

    cells = extract_transition_cells(sheet, count=5)

    assert len(cells) == 5
    assert [cell.getpixel((50, 50))[0] for cell in cells] == [1, 2, 3, 4, 5]


def test_extract_complete_cells_repacks_subjects_that_cross_grid_boundaries():
    sheet = Image.new("RGB", (300, 200), (0, 0, 255))
    draw = ImageDraw.Draw(sheet)
    subjects = [
        ((10, 15, 50, 85), (80, 120, 90)),
        ((85, 15, 125, 85), (110, 120, 90)),
        ((220, 15, 260, 85), (140, 120, 90)),
        ((80, 115, 120, 185), (170, 120, 90)),
        ((180, 115, 220, 185), (200, 120, 90)),
    ]
    for bbox, color in subjects:
        draw.rectangle(bbox, fill=color)

    cells = ai_transitions.extract_complete_transition_cells(sheet, count=5, margin=5)

    assert len(cells) == 5
    assert {cell.size for cell in cells} == {(100, 100)}
    assert [cell.getpixel((50, 50))[0] for cell in cells] == [80, 110, 140, 170, 200]
    for cell in cells:
        bbox = cell.getchannel("A").getbbox()
        assert bbox is not None
        assert 5 <= bbox[0] < bbox[2] <= 95
        assert 5 <= bbox[1] < bbox[3] <= 95


def test_interpolate_bbox_uses_smoothstep_motion():
    start = (10, 100, 110, 300)
    end = (50, 20, 250, 220)

    assert interpolate_bbox(start, end, 0.0) == start
    assert interpolate_bbox(start, end, 1.0) == end
    assert interpolate_bbox(start, end, 0.5) == (30, 60, 180, 260)


def test_render_transition_cell_removes_blue_and_cleans_hidden_rgb():
    cell = Image.new("RGB", (100, 100), (0, 0, 255))
    ImageDraw.Draw(cell).ellipse((20, 10, 80, 90), fill=(230, 160, 90))

    rendered = render_transition_cell(cell, (100, 200, 300, 600))

    assert rendered.mode == "RGBA"
    assert rendered.size == FRAME_SIZE
    assert rendered.getbbox() is not None
    left, top, right, bottom = rendered.getbbox()
    assert 100 <= left < right <= 300
    assert 200 <= top < bottom <= 600
    assert all(
        (red, green, blue) == (0, 0, 0)
        for red, green, blue, alpha in rendered.getdata()
        if alpha == 0
    )


def test_render_transition_cell_despills_blue_boundary_without_touching_interior():
    cell = Image.new("RGB", (20, 20), (0, 0, 255))
    draw = ImageDraw.Draw(cell)
    draw.rectangle((4, 4, 15, 15), fill=(180, 180, 255))
    draw.rectangle((6, 6, 13, 13), fill=(230, 160, 90))

    rendered = render_transition_cell(cell, (120, 220, 320, 620))

    assert not any(
        alpha > 0 and blue > max(red, green) + 12
        for red, green, blue, alpha in rendered.getdata()
    )
    center = rendered.getpixel((220, 520))
    assert center[:3] == (230, 160, 90)


def test_render_transition_cell_keeps_only_largest_subject_component():
    cell = Image.new("RGB", (100, 100), (0, 0, 255))
    draw = ImageDraw.Draw(cell)
    draw.rectangle((20, 20, 70, 90), fill=(230, 160, 90))
    draw.rectangle((82, 3, 91, 12), fill=(230, 160, 90))

    rendered = render_transition_cell(cell, (100, 200, 300, 600))
    alpha = rendered.getchannel("A")
    visited: set[tuple[int, int]] = set()
    components = 0
    for y in range(alpha.height):
        for x in range(alpha.width):
            if (x, y) in visited or alpha.getpixel((x, y)) == 0:
                continue
            components += 1
            pending = [(x, y)]
            visited.add((x, y))
            while pending:
                current_x, current_y = pending.pop()
                for neighbor_y in range(max(0, current_y - 1), min(alpha.height, current_y + 2)):
                    for neighbor_x in range(max(0, current_x - 1), min(alpha.width, current_x + 2)):
                        point = (neighbor_x, neighbor_y)
                        if point in visited or alpha.getpixel(point) == 0:
                            continue
                        visited.add(point)
                        pending.append(point)

    assert components == 1


def test_assemble_action_creates_thirty_frames_and_preserves_keyframe_bytes(tmp_path: Path):
    keyframes, sources = make_action_fixture(tmp_path)
    output = tmp_path / "out"
    qa = tmp_path / "qa"
    keyframe_bytes = {
        path.name: path.read_bytes() for path in sorted(keyframes.glob("*.png"))
    }

    report = assemble_action(keyframes, sources, output, qa, "jump")

    assert INTERMEDIATE_COUNTS == (5, 5, 4, 5, 5)
    assert FINAL_POSITIONS == (0, 6, 12, 17, 23, 29)
    assert [path.name for path in sorted(output.glob("*.png"))] == [
        f"{index:02d}.png" for index in range(30)
    ]
    for source_index, final_index in enumerate(FINAL_POSITIONS):
        assert (output / f"{final_index:02d}.png").read_bytes() == keyframe_bytes[
            f"{source_index:02d}.png"
        ]
    assert report["action"] == "jump"
    assert report["frame_count"] == 30
    assert set(report["artifacts"]) == {
        "contact-sheet.png",
        "normal.gif",
        "slow.gif",
        "stats.json",
    }

# 90-Frame Animation Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve 18 approved cat keyframes byte-for-byte, generate 72 continuous transitions, and validate three 30-frame 512×768 RGBA actions.

**Architecture:** A Pillow-only archive and validator define the permanent contract. An offline OpenCV/Numpy tool performs premultiplied-alpha bidirectional motion compensation; three agents run it independently for jump, squash, and shake. Runtime code loads only PNGs.

**Tech Stack:** Python 3.12, Pillow 11, Numpy, opencv-python-headless, pytest, SHA-256, JSON, GIF/PNG.

## Global Constraints

- Final assets are exactly 90 PNGs: three actions, each `00.png` through `29.png`.
- Every frame is `512×768 RGBA` with transparent background and opaque subject pixels.
- Original frames remain byte-identical at `00/06/12/17/23/29`; record their SHA-256 first.
- Add `5/5/4/5/5` frames between keys, exactly 24 new frames per action.
- Use premultiplied-alpha motion compensation; plain cross-fades and Alpha binarization are forbidden.
- Alpha-0 pixels have RGB `(0,0,0)` and the outer border is fully transparent.
- OpenCV/Numpy are offline-only; do not import them under `src/desktop_pet` or bundle them.
- Each action produces a contact sheet, 33ms GIF, 132ms GIF, and statistics JSON.
- Each generation agent writes only its assigned action and matching `qa/<action>` directory.

---

### Task 1: Immutable Keyframe Archive

**Files:** Create `tools/keyframes.py`, `tests/test_keyframes.py`, `assets/keyframes/manifest.json`, and `assets/keyframes/<action>/00.png` through `05.png`.

**Interfaces:** `archive_keyframes(source_root: Path, archive_root: Path) -> dict[str, object]`; manifest entries contain `sha256`, `size`, and `final_name`.

- [ ] **Step 1: Write failing archive tests**

```python
def test_archive_copies_bytes_and_records_mapping(tmp_path: Path):
    source = make_six_frame_source(tmp_path / "pet")
    archive = tmp_path / "keyframes"
    manifest = archive_keyframes(source, archive)
    assert manifest["final_positions"] == [0, 6, 12, 17, 23, 29]
    for action in ACTIONS:
        for index in range(6):
            name = f"{index:02d}.png"
            assert (archive/action/name).read_bytes() == (source/action/name).read_bytes()
            assert len(manifest["actions"][action][name]["sha256"]) == 64

def test_archive_refuses_changed_keyframe(tmp_path: Path):
    source = make_six_frame_source(tmp_path / "pet")
    archive = tmp_path / "keyframes"
    archive_keyframes(source, archive)
    (source/"jump"/"00.png").write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="keyframe mismatch"):
        archive_keyframes(source, archive)
```

- [ ] **Step 2: Verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_keyframes.py -q`

Expected: `ModuleNotFoundError: No module named 'tools.keyframes'`.

- [ ] **Step 3: Implement archive and CLI**

```python
ACTIONS = ("jump", "squash", "shake")
FINAL_POSITIONS = (0, 6, 12, 17, 23, 29)

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def archive_keyframes(source_root: Path, archive_root: Path) -> dict[str, object]:
    manifest = {"version": 1, "frame_size": [512, 768],
                "final_positions": list(FINAL_POSITIONS), "actions": {}}
    for action in ACTIONS:
        entries = {}
        target_dir = archive_root/action
        target_dir.mkdir(parents=True, exist_ok=True)
        for index, final_index in enumerate(FINAL_POSITIONS):
            name = f"{index:02d}.png"
            source, target = source_root/action/name, target_dir/name
            if target.exists() and target.read_bytes() != source.read_bytes():
                raise RuntimeError(f"keyframe mismatch: {action}/{name}")
            if not target.exists():
                shutil.copy2(source, target)
            entries[name] = {"sha256": sha256_file(target),
                             "size": target.stat().st_size,
                             "final_name": f"{final_index:02d}.png"}
        manifest["actions"][action] = entries
    (archive_root/"manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return manifest
```

- [ ] **Step 4: Verify GREEN and archive real files**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_keyframes.py -q`

Expected: all pass.

Run: `.\.venv\Scripts\python.exe -m tools.keyframes assets\pet assets\keyframes`

Expected: `OK: archived 18 immutable keyframes`.

- [ ] **Step 5: Commit**

```powershell
git add tools/keyframes.py tests/test_keyframes.py assets/keyframes
git commit -m "assets: archive immutable animation keyframes"
```

### Task 2: 30-Frame Runtime and Validator Contract

**Files:** Modify `src/desktop_pet/assets.py`, `tests/test_assets.py`, `tools/validate_assets.py`; create `tests/test_validate_assets.py`.

**Interfaces:** `FRAME_COUNT = 30`; `validate_assets(root: Path, keyframe_root: Path | None = None) -> dict[str, object]` returns `errors`, `actions`, `total_frames`.

- [ ] **Step 1: Write failing 30-frame tests**

```python
def test_find_frame_paths_requires_exact_thirty(tmp_path: Path):
    make_action(tmp_path/"jump", count=29)
    with pytest.raises(RuntimeError, match="30"):
        find_frame_paths(tmp_path, "jump")

def test_load_frames_returns_three_thirty_frame_actions():
    frames = load_frames()
    assert set(frames) == {"jump", "squash", "shake"}
    assert {len(value) for value in frames.values()} == {30}

def test_validator_rejects_changed_mapped_keyframe(tmp_path: Path):
    pet, keys = make_valid_thirty_frame_tree(tmp_path)
    Image.new("RGBA", (512, 768), (255, 0, 0, 255)).save(pet/"jump"/"06.png")
    report = validate_assets(pet, keys)
    assert any("SHA-256" in error for error in report["errors"])
```

- [ ] **Step 2: Verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_assets.py tests\test_validate_assets.py -q`

Expected: old six-frame assertions fail and the validator lacks `keyframe_root`.

- [ ] **Step 3: Implement exact naming and report checks**

```python
FRAME_COUNT = 30
EXPECTED_NAMES = tuple(f"{index:02d}.png" for index in range(FRAME_COUNT))

def find_frame_paths(root: Path, action: str) -> list[Path]:
    paths = sorted((root/action).glob("*.png"))
    if tuple(path.name for path in paths) != EXPECTED_NAMES:
        raise RuntimeError(
            f"{action} must contain exactly 30 frames named 00.png through 29.png")
    return paths

def transparent_rgb_is_zero(image: Image.Image) -> bool:
    return all((r, g, b) == (0, 0, 0)
               for r, g, b, a in image.convert("RGBA").getdata() if a == 0)

def border_is_transparent(image: Image.Image) -> bool:
    alpha = image.getchannel("A")
    top = alpha.crop((0, 0, alpha.width, 1)).getbbox()
    bottom = alpha.crop((0, alpha.height-1, alpha.width, alpha.height)).getbbox()
    left = alpha.crop((0, 0, 1, alpha.height)).getbbox()
    right = alpha.crop((alpha.width-1, 0, alpha.width, alpha.height)).getbbox()
    return not any((top, bottom, left, right))
```

The validator also checks RGBA, 512×768, Alpha extrema, manifest-mapped SHA-256, and writes JSON for `--report`. It prints `OK: 3 actions, 90 frames, 512x768 RGBA` only with no errors.

- [ ] **Step 4: Verify GREEN and commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_assets.py tests\test_validate_assets.py -q`

Expected: all pass.

```powershell
git add src/desktop_pet/assets.py tests/test_assets.py tools/validate_assets.py tests/test_validate_assets.py
git commit -m "test: require thirty frames per animation"
```

### Task 3: Premultiplied-Alpha Interpolator and QA Writer

**Files:** Create `requirements-assets.txt`, `tools/interpolate_action.py`, `tools/animation_qa.py`, `tests/test_interpolate_action.py`, `tests/test_animation_qa.py`.

**Interfaces:** `INTERMEDIATE_COUNTS = (5,5,4,5,5)`; `interpolate_pair(first, second, count) -> list[Image.Image]`; `build_action(keyframe_dir, output_dir, qa_dir, action) -> dict[str, object]`.

- [ ] **Step 1: Write failing deterministic tests**

```python
def test_interpolate_pair_moves_monotonically_and_cleans_hidden_rgb():
    frames = interpolate_pair(moving_square(8), moving_square(24), 5)
    assert len(frames) == 5
    centers = [alpha_centroid(frame)[0] for frame in frames]
    assert centers == sorted(centers)
    for frame in frames:
        assert all((r, g, b) == (0, 0, 0)
                   for r, g, b, a in frame.getdata() if a == 0)

def test_build_action_preserves_keyframe_bytes(tmp_path: Path):
    keys = make_keyframes(tmp_path/"keys")
    output = tmp_path/"out"
    build_action(keys, output, tmp_path/"qa", "jump")
    assert [p.name for p in sorted(output.glob("*.png"))] == [f"{i:02d}.png" for i in range(30)]
    for source, final in enumerate((0, 6, 12, 17, 23, 29)):
        assert (output/f"{final:02d}.png").read_bytes() == (keys/f"{source:02d}.png").read_bytes()

def test_qa_writer_creates_required_artifacts(tmp_path: Path):
    report = write_action_qa(make_thirty_frames(), tmp_path, "jump")
    assert set(report["artifacts"]) == {"contact-sheet.png", "normal.gif", "slow.gif", "stats.json"}
```

- [ ] **Step 2: Verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_interpolate_action.py tests\test_animation_qa.py -q`

Expected: missing interpolation and QA modules.

- [ ] **Step 3: Add offline dependencies and motion compensation**

`requirements-assets.txt` contains:

```text
numpy>=2.0,<3
opencv-python-headless>=4.10,<5
```

```python
INTERMEDIATE_COUNTS = (5, 5, 4, 5, 5)
FINAL_POSITIONS = (0, 6, 12, 17, 23, 29)

def smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)

def interpolate_pair(first: Image.Image, second: Image.Image,
                     count: int) -> list[Image.Image]:
    if first.size != (512, 768) or second.size != (512, 768):
        raise ValueError("interpolation requires 512x768 frames")
    forward, backward = bidirectional_flow(first, second)
    return [render_between(first, second, forward, backward,
                           smoothstep(step/(count+1)))
            for step in range(1, count+1)]
```

`bidirectional_flow` uses Farneback flow on grayscale composites plus Alpha. `render_between` converts endpoints to float32 premultiplied RGBA, remaps both toward `t`, blends valid warped samples with warped Alpha weights, unpremultiplies only nonzero Alpha, and zeros hidden RGB. `build_action` uses `shutil.copy2` for all six key positions so their PNG bytes never change.

- [ ] **Step 4: Implement QA outputs**

`write_action_qa` writes `contact-sheet.png`, `normal.gif` at 33ms, `slow.gif` at 132ms, and `stats.json`. Per-frame JSON includes SHA-256, Alpha bbox, centroid, effective area, largest-component ratio, edge-chroma count, and adjacent aligned-mask IoU.

- [ ] **Step 5: Verify GREEN and commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_interpolate_action.py tests\test_animation_qa.py -q`

Expected: all pass deterministically.

```powershell
git add requirements-assets.txt tools/interpolate_action.py tools/animation_qa.py tests/test_interpolate_action.py tests/test_animation_qa.py
git commit -m "feat: add alpha-aware animation interpolation"
```

### Task 4: Parallel Action Generation

**Files:** `jump_frames` exclusively writes `assets/pet/jump` and `qa/jump`; `squash_frames` writes `assets/pet/squash` and `qa/squash`; `shake_frames` writes `assets/pet/shake` and `qa/shake`.

**Interfaces:** Consumes Tasks 1 and 3; produces three isolated 30-frame directories and twelve QA artifacts.

- [ ] **Step 1: Install offline-only dependencies**

Run: `.\.venv\Scripts\python.exe -m pip install -r requirements-assets.txt`

Expected: `import numpy, cv2` succeeds in the development environment.

- [ ] **Step 2: Dispatch the three existing agents concurrently**

```powershell
.\.venv\Scripts\python.exe -m tools.interpolate_action --action jump --keyframes assets\keyframes\jump --output assets\pet\jump --qa qa\jump
.\.venv\Scripts\python.exe -m tools.interpolate_action --action squash --keyframes assets\keyframes\squash --output assets\pet\squash --qa qa\squash
.\.venv\Scripts\python.exe -m tools.interpolate_action --action shake --keyframes assets\keyframes\shake --output assets\pet\shake --qa qa\shake
```

Each agent records source hashes, checks normal and slow GIFs frame-by-frame, writes `qa/<action>/agent-report.md`, and reports 30 frames, four QA artifacts, six hashes unchanged, and no out-of-scope writes.

- [ ] **Step 3: Review and commit integrated outputs**

```powershell
git add assets/pet/jump assets/pet/squash assets/pet/shake qa/jump qa/squash qa/shake
git commit -m "assets: expand desktop pet actions to thirty frames"
```

### Task 5: Integrated 90-Frame Gate

**Files:** Create `tools/build_animation_qa.py`, `tests/test_build_animation_qa.py`, `qa/all-actions-contact-sheet.png`, `qa/asset-validation.json`; modify `build.ps1`.

**Interfaces:** `build_overview(asset_root: Path, output: Path) -> None`; build invokes validator with keyframe archive and JSON report.

- [ ] **Step 1: Write failing overview test**

```python
def test_build_overview_contains_three_rows_of_thirty(tmp_path: Path):
    assets = make_valid_assets(tmp_path/"pet")
    output = tmp_path/"overview.png"
    build_overview(assets, output)
    with Image.open(output) as image:
        assert image.size == (30*128, 3*220)
```

- [ ] **Step 2: Verify RED, implement, and verify GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_build_animation_qa.py -q`

Expected RED: missing `tools.build_animation_qa`; expected GREEN after implementation: pass.

`build.ps1` runs `tools\validate_assets.py assets\pet --keyframes assets\keyframes --report qa\asset-validation.json` before pytest and PyInstaller.

- [ ] **Step 3: Run the complete asset gate**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools\validate_assets.py assets\pet --keyframes assets\keyframes --report qa\asset-validation.json
.\.venv\Scripts\python.exe -m tools.build_animation_qa assets\pet qa\all-actions-contact-sheet.png
Select-String -Path src\desktop_pet\*.py -Pattern 'numpy|cv2|opencv'
```

Expected: tests pass; validator prints `OK: 3 actions, 90 frames, 512x768 RGBA`; overview exists; all 18 hashes match; source scan returns no matches.

- [ ] **Step 4: Commit**

```powershell
git add tools/build_animation_qa.py tests/test_build_animation_qa.py qa/all-actions-contact-sheet.png qa/asset-validation.json build.ps1
git commit -m "build: verify ninety animation frames"
```

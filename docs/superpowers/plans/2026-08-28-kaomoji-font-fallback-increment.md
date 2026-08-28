# 精致颜文字与双字体回退增量实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有六帧猫耳气泡桌宠上加入每动作 20 条精致颜文字、Noto Sans/Noto Sans Math 确定性逐字符回退，并重新构建可双击运行的最终 EXE。

**Architecture:** 保留现有 `BubbleWindow + LayeredWindowRenderer` 逐像素 Alpha 架构，新建独立 `font_runs.py` 作为字体 cmap、run 分段、测宽和绘制的唯一实现。`dialogue.py` 先把每条内容分类为中文或纯颜文字，再应用不同配额、字体和宽度规则；`BubbleComposer` 只消费共享布局结果。构建门验证源码资源、PyInstaller 归档和真实桌面交互三层证据。

**Tech Stack:** Python 3.11+、Pillow 11.x、fonttools 4.x、Tkinter、Win32 `UpdateLayeredWindow`、pytest 8.x、PyInstaller 6.x、Windows PowerShell 5.1。

## Global Constraints

- 工作树固定为 `C:\Users\rog\Documents\桌面宠物\.worktrees\desktop-pet-6-frame-alpha`，分支固定为 `codex/desktop-pet-6-frame-alpha`。
- 三组动作仍各 6 帧；不修改 18 张 `512x768 RGBA` 角色关键帧、动作顺序或角色逐像素 Alpha 窗口。
- 每动作恰好 180 条原中文 + 20 条纯颜文字；总计 600 条，全局唯一。
- 每条按 Python `len(text)` 为 6–10 个 Unicode code points；全库至少 540 条为 7–9 码位。
- 中文使用内置 `ZCOOLKuaiLe-Regular.ttf` 28px，宽度 120–230px；颜文字使用内置 Noto 回退链 40px，宽度 60–230px。
- Noto Sans Variable 固定 `wght=400`、`wdth=100`，覆盖优先级固定为 Noto Sans，再到 Noto Sans Math；两者均缺字时闭锁失败。
- 比例 1.0 的文字安全矩形固定为 `(25, 52, 255, 100)`，最终 ink bbox 只允许 1px 取整容差。
- 禁止 Tk 字体、`ImageFont.load_default()`、Windows Fonts API、系统字体家族查找及 `.notdef` 方框回退。
- 最终 EXE 继续为单文件、无控制台、可直接双击运行；气泡仍为猫耳蝴蝶结图片皮肤和逐像素 Alpha。
- `.superpowers/sdd/progress.md` 是实施进度的唯一账本；旧计划 `2026-08-28-cat-ear-bubble-dialogue-library.md` 只作历史参考。

---

## 文件结构

- 新建 `src/desktop_pet/font_runs.py`：加载内置字体、读取真实 cmap、固定 Variable Font 轴值、分段、布局和绘制。
- 修改 `src/desktop_pet/dialogue.py`：纯颜文字分类、180+20 配额、类别化字体与宽度验证。
- 修改 `src/desktop_pet/bubble.py`：按类别选择 28px/40px resolver，并绘制共享布局结果。
- 新建 `tools/apply_kaomoji_dialogue.py`：按固定索引保留 540 条中文并写入已审定 60 条颜文字。
- 修改 `tools/validate_dialogue.py`：输出中文/颜文字计数、两类宽度统计和缺字结果。
- 新建 `tools/verify_release_archive.py`：核对 PyInstaller 单文件归档中的字体、许可、台词、气泡和关键帧。
- 修改 `assets/dialogue/phrases.json`、`assets/fonts/`、`THIRD_PARTY_NOTICES.txt`、`desktop_pet.spec`、`build.ps1`、`README.md`。
- 新建或修改 `tests/test_font_runs.py`、`tests/test_font_assets.py`、`tests/test_dialogue.py`、`tests/test_bubble.py`、`tests/test_build_script.py`、`tests/test_release_archive.py`。

---

### Task 1: 固定三套字体、许可和依赖

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/test_font_assets.py`
- Create: `assets/fonts/NotoSans-Variable.ttf`
- Create: `assets/fonts/NotoSansMath-Regular.ttf`
- Create: `assets/fonts/licenses/ZCOOLKuaiLe-OFL-1.1.txt`
- Create: `assets/fonts/licenses/NotoSans-OFL-1.1.txt`
- Create: `assets/fonts/licenses/NotoSansMath-OFL-1.1.txt`
- Delete: `assets/fonts/OFL.txt`
- Modify: `THIRD_PARTY_NOTICES.txt`

**Interfaces:**
- Consumes: 已有 `asset_path(*parts) -> Path`。
- Produces: 三个固定字体路径、三个固定许可路径，以及运行时依赖 `fonttools>=4.59,<5`。

- [ ] **Step 1: 扩写字体资产失败测试**

把 `tests/test_font_assets.py` 的资产表改为：

```python
EXPECTED_FONT_ASSETS = (
    ("ZCOOLKuaiLe-Regular.ttf", 1_514_968,
     "812a6fc1fe54b6d73a419245c32dfeba8aa33104d5be90d1cf6af082007cb71d"),
    ("NotoSans-Variable.ttf", 2_049_096,
     "bfb7bb691513f12e734dc346c03a03f784912432d7e3fa8e56efcf906fe86b3d"),
    ("NotoSansMath-Regular.ttf", 1_015_396,
     "3f495fe933c06786e4d5f6d86b8ee70b6753a68ee3b9d87528726de0f6e2c47d"),
)
EXPECTED_LICENSE_ASSETS = (
    ("ZCOOLKuaiLe-OFL-1.1.txt", 4_398,
     "538078469839b4a2e7ad22bef4ebe41681a4e53749bb2a072144024f1d6d703d"),
    ("NotoSans-OFL-1.1.txt", 4_396,
     "cee9892f9f0cc8fe882c9e9537ee6a89621d86ee7ceaf70b02e2b2b1c25c061a"),
    ("NotoSansMath-OFL-1.1.txt", 4_380,
     "403a95275b469061b7d4371c328e0ada3bc7d63328abe2e88aad5cd243b2fe21"),
)

@pytest.mark.parametrize(("filename", "size", "digest"), EXPECTED_FONT_ASSETS)
def test_bundled_font_binaries_match_pinned_google_fonts(filename, size, digest):
    path = asset_path("assets", "fonts", filename)
    assert path.stat().st_size == size
    assert sha256(path.read_bytes()).hexdigest() == digest

@pytest.mark.parametrize(("filename", "size", "digest"), EXPECTED_LICENSE_ASSETS)
def test_bundled_font_licenses_match_pinned_google_fonts(filename, size, digest):
    path = asset_path("assets", "fonts", "licenses", filename)
    assert path.stat().st_size == size
    assert sha256(path.read_bytes()).hexdigest() == digest

def test_notice_lists_every_pinned_font_and_license():
    notice = asset_path("THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")
    for filename, size, digest in (*EXPECTED_FONT_ASSETS, *EXPECTED_LICENSE_ASSETS):
        assert filename in notice
        assert str(size) in notice
        assert digest in notice.lower()
```

- [ ] **Step 2: 运行测试确认缺少 Noto 资产**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_font_assets.py -q
```

Expected: FAIL，至少报告 `NotoSans-Variable.ttf` 不存在。

- [ ] **Step 3: 放入已核验字体和三份固定许可**

使用明确文件，不从系统字体目录复制：

```powershell
New-Item -ItemType Directory -Force -Path assets\fonts\licenses
Copy-Item -LiteralPath C:\Users\rog\AppData\Local\Temp\codex-pet-NotoSans-Variable.ttf -Destination assets\fonts\NotoSans-Variable.ttf
Copy-Item -LiteralPath C:\Users\rog\AppData\Local\Temp\codex-pet-NotoSansMath-Regular.ttf -Destination assets\fonts\NotoSansMath-Regular.ttf
Copy-Item -LiteralPath assets\fonts\OFL.txt -Destination assets\fonts\licenses\ZCOOLKuaiLe-OFL-1.1.txt
Copy-Item -LiteralPath C:\Users\rog\AppData\Local\Temp\codex-pet-NotoSans-OFL.txt -Destination assets\fonts\licenses\NotoSans-OFL-1.1.txt
Copy-Item -LiteralPath C:\Users\rog\AppData\Local\Temp\codex-pet-NotoSansMath-OFL.txt -Destination assets\fonts\licenses\NotoSansMath-OFL-1.1.txt
Remove-Item -LiteralPath assets\fonts\OFL.txt
```

随后用 `Get-FileHash -Algorithm SHA256` 校验六个文件，任何值不匹配立即停止。

- [ ] **Step 4: 固定依赖与 notice 内容**

在 `pyproject.toml` 中改为：

```toml
dependencies = ["Pillow>=11,<12", "fonttools>=4.59,<5"]
```

在 `THIRD_PARTY_NOTICES.txt` 中为三套字体分别写明本地名、官方 URL、字节数、SHA-256 和对应 OFL 路径。Noto URL 固定为：

```text
https://raw.githubusercontent.com/google/fonts/main/ofl/notosans/NotoSans%5Bwdth,wght%5D.ttf
https://raw.githubusercontent.com/google/fonts/main/ofl/notosansmath/NotoSansMath-Regular.ttf
https://raw.githubusercontent.com/google/fonts/main/ofl/notosans/OFL.txt
https://raw.githubusercontent.com/google/fonts/main/ofl/notosansmath/OFL.txt
```

- [ ] **Step 5: 安装项目依赖并运行字体测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests\test_font_assets.py -q
```

Expected: 字体资产测试全部 PASS；0 failed。

- [ ] **Step 6: 提交字体资产闭环**

```powershell
git add pyproject.toml tests\test_font_assets.py assets\fonts THIRD_PARTY_NOTICES.txt
git commit -m "assets: bundle deterministic kaomoji fonts"
```

---

### Task 2: 建立共享 FontRunResolver

**Files:**
- Create: `src/desktop_pet/font_runs.py`
- Create: `tests/test_font_runs.py`

**Interfaces:**
- Consumes: `asset_path`, Pillow `ImageFont`/`ImageDraw`, fontTools `TTFont`。
- Produces: `FontRunResolver.for_chinese(size)`, `FontRunResolver.for_kaomoji(size)`, `layout(text, context="") -> TextLayout`，`draw_layout(draw, layout, safe_rect, fill) -> tuple[int, int, int, int]`。

- [ ] **Step 1: 写 cmap、优先级、缺字和实际 bbox 的失败测试**

新建 `tests/test_font_runs.py`：

```python
import pytest
from PIL import Image, ImageDraw

from desktop_pet.font_runs import FontRunResolver, MissingGlyphError, draw_layout


def test_kaomoji_resolver_splits_user_sample_with_fixed_priority():
    layout = FontRunResolver.for_kaomoji(40).layout("₍^. .^₎⟆", context="jump")
    assert [run.font_key for run in layout.runs] == ["noto_sans", "noto_math"]
    assert layout.runs[-1].text == "⟆"
    assert layout.total_advance <= 230


def test_character_present_in_both_fonts_uses_noto_sans():
    layout = FontRunResolver.for_kaomoji(40).layout("(^.^)")
    assert {run.font_key for run in layout.runs} == {"noto_sans"}


def test_missing_character_fails_with_context_and_codepoint():
    with pytest.raises(MissingGlyphError, match=r"shake.*U\+10FFFF"):
        FontRunResolver.for_kaomoji(40).layout("(^.^)\U0010ffff", context="shake")


def test_drawn_pixels_equal_reported_shared_ink_bbox():
    resolver = FontRunResolver.for_kaomoji(40)
    layout = resolver.layout("₍^. .^₎⟆")
    image = Image.new("L", (280, 140), 0)
    bbox = draw_layout(ImageDraw.Draw(image), layout, (25, 52, 255, 100), 255)
    actual = image.getbbox()
    assert actual is not None
    assert all(abs(actual[index] - bbox[index]) <= 1 for index in range(4))
    assert bbox[0] >= 24 and bbox[2] <= 256
    assert bbox[1] >= 51 and bbox[3] <= 101
```

- [ ] **Step 2: 运行测试确认模块尚不存在**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_font_runs.py -q
```

Expected: collection FAIL with `ModuleNotFoundError: desktop_pet.font_runs`。

- [ ] **Step 3: 实现唯一 cmap/run/layout 模块**

`src/desktop_pet/font_runs.py` 使用以下完整接口和数据模型：

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from fontTools.ttLib import TTFont
from PIL import ImageDraw, ImageFont

from .paths import asset_path


class MissingGlyphError(ValueError):
    pass


@dataclass(frozen=True)
class FontFace:
    key: str
    path: Path
    font: ImageFont.FreeTypeFont
    codepoints: frozenset[int]


@dataclass(frozen=True)
class FontRun:
    font_key: str
    text: str
    font: ImageFont.FreeTypeFont
    x_advance: float
    advance: float
    ink_bbox: tuple[int, int, int, int]


@dataclass(frozen=True)
class TextLayout:
    runs: tuple[FontRun, ...]
    total_advance: float
    ink_bbox: tuple[int, int, int, int]


def _cmap(path: Path) -> frozenset[int]:
    with TTFont(path, lazy=True, fontNumber=0) as source:
        return frozenset(
            codepoint
            for table in source["cmap"].tables
            if table.isUnicode()
            for codepoint in table.cmap
        )


def _face(key: str, path: Path, size: int, axes: list[float] | None = None) -> FontFace:
    font = ImageFont.truetype(path, size)
    if axes is not None:
        font.set_variation_by_axes(axes)
    return FontFace(key, path, font, _cmap(path))


class FontRunResolver:
    def __init__(self, faces: Iterable[FontFace]):
        self.faces = tuple(faces)
        if not self.faces:
            raise ValueError("font resolver needs at least one bundled face")

    @classmethod
    def for_chinese(cls, size: int) -> "FontRunResolver":
        path = asset_path("assets", "fonts", "ZCOOLKuaiLe-Regular.ttf")
        return cls((_face("zcool", path, size),))

    @classmethod
    def for_kaomoji(cls, size: int) -> "FontRunResolver":
        sans = asset_path("assets", "fonts", "NotoSans-Variable.ttf")
        math = asset_path("assets", "fonts", "NotoSansMath-Regular.ttf")
        return cls((
            _face("noto_sans", sans, size, [400.0, 100.0]),
            _face("noto_math", math, size),
        ))

    def layout(self, text: str, context: str = "") -> TextLayout:
        selected: list[tuple[FontFace, str]] = []
        for character in text:
            face = next((item for item in self.faces if ord(character) in item.codepoints), None)
            if face is None:
                prefix = f"{context}: " if context else ""
                raise MissingGlyphError(
                    f"{prefix}missing bundled glyph U+{ord(character):04X} in {text!r}"
                )
            if selected and selected[-1][0].key == face.key:
                selected[-1] = (face, selected[-1][1] + character)
            else:
                selected.append((face, character))

        runs: list[FontRun] = []
        cursor = 0.0
        union: tuple[int, int, int, int] | None = None
        for face, run_text in selected:
            bbox = face.font.getbbox(run_text, anchor="ls")
            positioned = (
                int(round(cursor + bbox[0])), bbox[1],
                int(round(cursor + bbox[2])), bbox[3],
            )
            union = positioned if union is None else (
                min(union[0], positioned[0]), min(union[1], positioned[1]),
                max(union[2], positioned[2]), max(union[3], positioned[3]),
            )
            advance = float(face.font.getlength(run_text))
            runs.append(FontRun(face.key, run_text, face.font, cursor, advance, positioned))
            cursor += advance
        return TextLayout(tuple(runs), cursor, union or (0, 0, 0, 0))


def draw_layout(
    draw: ImageDraw.ImageDraw,
    layout: TextLayout,
    safe_rect: tuple[int, int, int, int],
    fill: int | tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    left, top, right, bottom = safe_rect
    x0 = (left + right - layout.total_advance) / 2
    baseline = (top + bottom - layout.ink_bbox[1] - layout.ink_bbox[3]) / 2
    for run in layout.runs:
        draw.text((x0 + run.x_advance, baseline), run.text, font=run.font, fill=fill, anchor="ls")
    return (
        int(round(x0 + layout.ink_bbox[0])),
        int(round(baseline + layout.ink_bbox[1])),
        int(round(x0 + layout.ink_bbox[2])),
        int(round(baseline + layout.ink_bbox[3])),
    )
```

实现时对空文本返回空布局；字体缺失或损坏保留 `OSError`，不捕获并回退。

- [ ] **Step 4: 运行共享布局测试**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_font_runs.py -q
```

Expected: 全部 PASS；用户样例形成两个 run，0 failed。

- [ ] **Step 5: 提交字体 run 引擎**

```powershell
git add src\desktop_pet\font_runs.py tests\test_font_runs.py
git commit -m "feat: add deterministic bundled font runs"
```

---

### Task 3: 把台词库迁移为每动作 180+20

**Files:**
- Create: `tools/apply_kaomoji_dialogue.py`
- Modify: `assets/dialogue/phrases.json`
- Modify: `src/desktop_pet/dialogue.py`
- Modify: `tests/test_dialogue.py`
- Modify: `tools/validate_dialogue.py`

**Interfaces:**
- Consumes: `FontRunResolver`、现有源台词哈希 `927C4042...F36D3B2`。
- Produces: `is_kaomoji_phrase(text) -> bool`、`validate_phrase_rendering(pools) -> DialogueRenderStats`、最终 JSON 哈希 `829179B4...E4CDB`。

- [ ] **Step 1: 写 180+20、分类和字体统计失败测试**

在 `tests/test_dialogue.py` 中用这些断言替换“全部含第一人称”的旧断言：

```python
from desktop_pet.dialogue import (
    is_kaomoji_phrase,
    validate_phrase_rendering,
)


def test_packaged_dialogue_has_exact_180_chinese_and_20_kaomoji_per_action():
    pools = load_phrase_pools()
    for action, phrases in pools.items():
        kaomoji = [text for text in phrases if is_kaomoji_phrase(text)]
        chinese = [text for text in phrases if not is_kaomoji_phrase(text)]
        assert len(kaomoji) == 20
        assert len(chinese) == 180
        assert all(any(marker in text for marker in FIRST_PERSON_MARKERS) for text in chinese)


def test_user_kaomoji_style_is_packaged_and_uses_no_system_fallback():
    pools = load_phrase_pools()
    assert "₍^. .^₎⟆" in pools["jump"]
    assert is_kaomoji_phrase("₍^. .^₎⟆")


@pytest.mark.parametrize("text", ["猫猫冲呀(^.^)", "🎉(^.^)", "(^.^)\u200d", "ab(^.^)"])
def test_kaomoji_classifier_rejects_mixed_text_emoji_and_format_controls(text):
    assert not is_kaomoji_phrase(text)


def test_render_validation_reports_split_counts_and_widths():
    stats = validate_phrase_rendering(load_phrase_pools())
    assert stats.chinese_count == 540
    assert stats.kaomoji_count == 60
    assert 120 <= stats.chinese.minimum <= stats.chinese.maximum <= 230
    assert 60 <= stats.kaomoji.minimum <= stats.kaomoji.maximum <= 230
```

- [ ] **Step 2: 运行测试确认旧校验器拒绝纯颜文字**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_dialogue.py -q
```

Expected: FAIL，原因包含缺少 `is_kaomoji_phrase` 或纯颜文字缺第一人称。

- [ ] **Step 3: 创建可审计的固定迁移工具**

新建 `tools/apply_kaomoji_dialogue.py`，固定以下三组数组，每连续四条对应一个语义块：

```python
SOURCE_SHA256 = "927C40426F43C8AAB13FDB3C67C9A551D10B76299C4B82DCC6EDF3109F36D3B2"
FINAL_SHA256 = "829179B422184A92FAA9D164F839D7B8AB0233B08F4E24904961B43EA4CE4CDB"

KAOMOJI = {
    "jump": (
        "₍^. .^₎⟆", r"\(^.^)/", "/(^.^)\\", r"\(^▽^)/",
        "/(^▽^)\\", r"\(^◇^)/", "/(^◇^)\\", r"\(^o^)/",
        "/(^o^)\\", "⌒(^.^)⌒", "⌒(^▽^)⌒", "⌒(^◇^)⌒",
        "o(^.^)o", "O(^.^)O", "o(^▽^)o", "O(^▽^)O",
        r"\(=^.^=)/", "/(=^.^=)\\", "⌒(=^.^=)⌒", "o(=^▽^=)o",
    ),
    "squash": (
        "(=^.^=)", "(=^..^=)", "(=^-.-^=)", "(=x.x=)",
        "(=o.o=)", "(=^_^=)", "(=>.<=)", "(=;.;=)",
        "(=~.~=)", "(=u.u=)", "(=-.-=)", "(=^o^=)",
        "(=^3^=)", "(=._.=)", "(=O.O=)", "₍^. .^₎",
        "₍- . -₎", "₍x . x₎", "₍o . o₎", "₍> . <₎",
    ),
    "shake": (
        "(^._.^)~", "~(^._.^)", "(=^.^=)~", "~(=^.^=)",
        "~(=^.^=)~", "((^.^))", "((=^.^=))", "(@_@;)",
        "(x_x;)", "(o_o;)", "(>_<;)", "(=;o;=)",
        "(=;_;=)", "(=x_x=)", "(^.^)~~", "~~(^.^)",
        "(=^.^=)>", "<(=^.^=)", ">(=x.x=)<", "~(=x.x=)~",
    ),
}
```

迁移主体固定为：

```python
def migrate(pools: dict[str, list[str]]) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    for action in ("jump", "squash", "shake"):
        result: list[str] = []
        for block in range(5):
            start = block * 40
            result.extend(pools[action][start:start + 36])
            result.extend(KAOMOJI[action][block * 4:block * 4 + 4])
        output[action] = result
    return output
```

CLI 必须先校验输入文件 SHA-256 等于 `SOURCE_SHA256`，以 `ensure_ascii=False, indent=2` 加末尾换行写回，再校验输出等于 `FINAL_SHA256`。输入已是最终哈希时只做验证并返回 0。

- [ ] **Step 4: 实现分类、配额与分类化渲染验证**

在 `dialogue.py` 中新增固定结构：

```python
KAOMOJI_PER_ACTION = 20
CHINESE_PER_ACTION = 180
CHINESE_WIDTH_RANGE = (120, 230)
KAOMOJI_WIDTH_RANGE = (60, 230)
KAOMOJI_ALLOWED = frozenset("₍₎⟆()^._ -\\/▽◇oOx=<>;~u3@⌒")


def is_kaomoji_phrase(text: str) -> bool:
    if not isinstance(text, str) or text != text.strip() or not 6 <= len(text) <= 10:
        return False
    if not set(text) <= KAOMOJI_ALLOWED:
        return False
    if any(unicodedata.category(ch).startswith("C") or unicodedata.combining(ch) for ch in text):
        return False
    if re.search(r"[A-Za-z]{2}", text):
        return False
    return (("(" in text and ")" in text) or ("₍" in text and "₎" in text)) and any(
        eye in text for eye in ("^", "x", "o", "O", "@", ">", "<", ";", "-")
    )
```

`validate_phrase_pools` 先分类，每动作断言正好 20/180；只对中文类执行第一人称检查。新增 `WidthStats` 与 `DialogueRenderStats` dataclass；`validate_phrase_rendering` 对中文调用 `FontRunResolver.for_chinese(28)`，对颜文字调用 `FontRunResolver.for_kaomoji(40)`，验证总 advance、48px 高度和空 bbox。

- [ ] **Step 5: 迁移 JSON 并核对固定结果**

```powershell
.\.venv\Scripts\python.exe tools\apply_kaomoji_dialogue.py assets\dialogue\phrases.json
Get-FileHash -Algorithm SHA256 assets\dialogue\phrases.json
```

Expected: SHA-256 为 `829179B422184A92FAA9D164F839D7B8AB0233B08F4E24904961B43EA4CE4CDB`；三组各 200，全局唯一 600，7–9 码位为 596 条。

- [ ] **Step 6: 更新 CLI 输出并运行聚焦测试**

`tools/validate_dialogue.py` 输出固定包含：

```text
jump: 180 Chinese + 20 kaomoji
squash: 180 Chinese + 20 kaomoji
shake: 180 Chinese + 20 kaomoji
Chinese width min/median/max: ...px
Kaomoji width min/median/max: ...px
dialogue validation passed: 600 unique phrases
```

Run:

```powershell
.\.venv\Scripts\python.exe tools\validate_dialogue.py
.\.venv\Scripts\python.exe -m pytest tests\test_dialogue.py -q
```

Expected: CLI exit 0；测试全部 PASS。

- [ ] **Step 7: 提交 600 条最终台词库**

```powershell
git add tools\apply_kaomoji_dialogue.py assets\dialogue\phrases.json src\desktop_pet\dialogue.py tests\test_dialogue.py tools\validate_dialogue.py
git commit -m "feat: add action-specific kaomoji dialogue pools"
```

---

### Task 4: 把共享 run 布局接入猫耳气泡

**Files:**
- Modify: `src/desktop_pet/bubble.py`
- Modify: `src/desktop_pet/bubble_layout.py`
- Modify: `tests/test_bubble.py`

**Interfaces:**
- Consumes: `is_kaomoji_phrase`、`FontRunResolver`、`draw_layout`。
- Produces: `BubbleComposer.render(text, tail_direction, scale)` 在 28px 中文和 40px 颜文字间确定性切换。

- [ ] **Step 1: 写颜文字字号、两 run 和安全矩形失败测试**

在 `tests/test_bubble.py` 新增：

```python
def test_composer_renders_user_kaomoji_inside_the_safe_rectangle():
    composer = BubbleComposer()
    image = composer.render("₍^. .^₎⟆", "down")
    blank = composer.render("", "down")
    text_bbox = ImageChops.difference(image.convert("RGB"), blank.convert("RGB")).getbbox()
    assert image.mode == "RGBA"
    assert text_bbox is not None
    left, top, right, bottom = text_bbox
    assert left >= 24 and right <= 256
    assert top >= 51 and bottom <= 101


def test_composer_renders_chinese_inside_the_same_safe_rectangle():
    composer = BubbleComposer()
    image = composer.render("猫猫今天要起飞", "up")
    blank = composer.render("", "up")
    text_bbox = ImageChops.difference(image.convert("RGB"), blank.convert("RGB")).getbbox()
    assert text_bbox is not None
    assert text_bbox[0] >= 24 and text_bbox[2] <= 256
    assert text_bbox[1] >= 51 and text_bbox[3] <= 101


def test_directional_output_sizes_match_approved_contract():
    composer = BubbleComposer()
    assert composer.size_for("down") == (280, 158)
    assert composer.size_for("up") == (280, 140)
    assert composer.size_for("left") == (280, 140)
    assert composer.size_for("right") == (280, 140)
```

- [ ] **Step 2: 运行测试确认 BubbleComposer 尚未支持 Noto run**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_bubble.py -q
```

Expected: FAIL，缺少 `last_text_kind` 或用户样例仍走 ZCOOL。

- [ ] **Step 3: 删除自动减字号并接入共享布局**

在 `bubble_layout.py` 新增：

```python
BUBBLE_KAOMOJI_FONT_SIZE = 40
CHINESE_MIN_WIDTH = 120
KAOMOJI_MIN_WIDTH = 60
```

在 `BubbleComposer.__init__` 中维护按 `(kind, size)` 缓存的 resolver。把旧 `_draw_text` 减字号循环替换为：

```python
kind = "kaomoji" if is_kaomoji_phrase(text) else "chinese"
base_size = BUBBLE_KAOMOJI_FONT_SIZE if kind == "kaomoji" else BUBBLE_FONT_SIZE
font_size = max(1, round(base_size * body_scale))
cache_key = (kind, font_size)
resolver = self._resolvers.get(cache_key)
if resolver is None:
    factory = FontRunResolver.for_kaomoji if kind == "kaomoji" else FontRunResolver.for_chinese
    resolver = self._resolvers.setdefault(cache_key, factory(font_size))
layout = resolver.layout(text, context=kind)
safe_rect = (
    body_offset[0] + left,
    body_offset[1] + top,
    body_offset[0] + right,
    body_offset[1] + bottom,
)
bbox = draw_layout(ImageDraw.Draw(image), layout, safe_rect, BUBBLE_TEXT_COLOR)
```

在绘制前验证 `layout.total_advance <= safe_width` 且 bbox 高度不超过安全区加 1px；失败抛 `ValueError`，绝不缩小比例 1.0 的单条内容。

- [ ] **Step 4: 运行 bubble、dialogue 和窗口回归测试**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_font_runs.py tests\test_dialogue.py tests\test_bubble.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_window.py -q -p no:cacheprovider --basetemp .superpowers\sdd\.pytest-kaomoji-window
```

Expected: 全部 PASS；0 failed；气泡位置、拖动跟随和置顶行为不回归。

- [ ] **Step 5: 生成四方向静态 QA 蒙版**

用项目 Python 调用 `BubbleComposer.render("₍^. .^₎⟆", direction)` 生成四张 RGBA，并拼成 `qa/kaomoji-bubble-directions.png`。检查透明角、无白矩形、无粉边、文字不碰猫耳和蝴蝶结。

- [ ] **Step 6: 提交气泡渲染整合**

```powershell
git add src\desktop_pet\bubble.py src\desktop_pet\bubble_layout.py tests\test_bubble.py qa\kaomoji-bubble-directions.png
git commit -m "feat: render kaomoji with bundled font fallback"
```

---

### Task 5: 加固 PyInstaller 归档与发布门

**Files:**
- Create: `tools/verify_release_archive.py`
- Create: `tests/test_release_archive.py`
- Modify: `tests/test_build_script.py`
- Modify: `desktop_pet.spec`
- Modify: `build.ps1`
- Modify: `README.md`

**Interfaces:**
- Consumes: PyInstaller `CArchiveReader`、最终资源树、单文件 EXE。
- Produces: `verify_archive(exe: Path, project_root: Path) -> None`，构建后不一致即非零退出。

- [ ] **Step 1: 写归档资源失败测试**

`tests/test_build_script.py` 新增：

```python
def test_build_verifies_archive_after_pyinstaller():
    script = Path("build.ps1").read_text(encoding="utf-8")
    build = script.index("-m PyInstaller")
    archive = script.index(r"tools\verify_release_archive.py")
    assert build < archive
```

`tests/test_release_archive.py` 用 fake reader 断言缺少 `assets/fonts/NotoSansMath-Regular.ttf` 时抛出包含该路径的 `ValueError`；用临时归档映射断言提取字节与工作区文件哈希不一致时失败。

- [ ] **Step 2: 运行测试确认归档验证器不存在**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_build_script.py tests\test_release_archive.py -q
```

Expected: FAIL，缺少 `tools.verify_release_archive` 或构建脚本调用。

- [ ] **Step 3: 实现单文件归档精确核对**

`tools/verify_release_archive.py` 的核心固定为：

```python
from PyInstaller.archive.readers import CArchiveReader


def verify_archive(exe: Path, project_root: Path) -> None:
    archive = CArchiveReader(str(exe))
    normalized = {name.replace("\\", "/"): name for name in archive.toc}
    required_files = [
        *sorted((project_root / "assets" / "keyframes").glob("*/*.png")),
        *sorted((project_root / "assets" / "bubble").glob("*.png")),
        *sorted((project_root / "assets" / "fonts").glob("*.ttf")),
        *sorted((project_root / "assets" / "fonts" / "licenses").glob("*.txt")),
        project_root / "assets" / "dialogue" / "phrases.json",
        project_root / "THIRD_PARTY_NOTICES.txt",
    ]
    for source in required_files:
        relative = source.relative_to(project_root).as_posix()
        archived_name = normalized.get(relative)
        if archived_name is None:
            raise ValueError(f"missing archive resource: {relative}")
        if archive.extract(archived_name) != source.read_bytes():
            raise ValueError(f"archive resource differs from source: {relative}")
```

CLI 接收一个 EXE 路径，成功输出关键帧 18、气泡 5、字体 3、许可 3、台词 1、notice 1 的核对结果。

- [ ] **Step 4: 修改 spec 与 build 发布门**

`desktop_pet.spec` 保持目录 datas，并确认 `assets/fonts` 递归包含 `licenses/`。把 EXE 名改为：

```python
name="桌面宠物-6帧猫耳颜文字版"
```

`build.ps1` 在 PyInstaller 成功后、输出摘要前调用：

```powershell
$expectedExe = Join-Path $projectRoot 'dist\桌面宠物-6帧猫耳颜文字版.exe'
& $python tools\verify_release_archive.py $expectedExe
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 单文件归档资源验证失败' }
```

构建脚本继续保留 UTF-8 BOM、pytest 临时目录安全校验和 `finally` 清理。

- [ ] **Step 5: 更新 README 的最终行为与许可说明**

README 必须明确：每动作 180 中文 + 20 颜文字、每次成功点击只从当前动作库随机一条、中文 28px、颜文字 40px、Noto 两字体逐字符 fallback、不安装系统字体、三份 OFL 位于 `交付\字体许可\`。

- [ ] **Step 6: 运行构建门聚焦测试并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_build_script.py tests\test_release_archive.py -q
git add tools\verify_release_archive.py tests\test_release_archive.py tests\test_build_script.py desktop_pet.spec build.ps1 README.md
git commit -m "build: verify packaged kaomoji release resources"
```

Expected: 测试全部 PASS；0 failed。

---

### Task 6: 完整构建、真实桌面 QA 与最终交付

**Files:**
- Modify: `.superpowers/sdd/progress.md`
- Create: `qa/cat-ear-bubble-runtime.png`
- Create: `qa/kaomoji-release-report.md`
- Create: `交付/桌面宠物-6帧猫耳颜文字版.exe`
- Create: `交付/台词库-600句.json`
- Create: `交付/THIRD_PARTY_NOTICES.txt`
- Create: `交付/字体许可/ZCOOLKuaiLe-OFL-1.1.txt`
- Create: `交付/字体许可/NotoSans-OFL-1.1.txt`
- Create: `交付/字体许可/NotoSansMath-OFL-1.1.txt`

**Interfaces:**
- Consumes: Tasks 1–5 的通过提交。
- Produces: 可双击 EXE、600 条 JSON、许可文件、哈希与真实桌面 QA 记录。

- [ ] **Step 1: 运行全套源码发布门**

```powershell
.\.venv\Scripts\python.exe tools\validate_assets.py assets\keyframes --keyframe-root assets\keyframes --frame-count 6 --keyframe-layout direct --report qa\six-frame-alpha-validation.json
.\.venv\Scripts\python.exe tools\validate_dialogue.py
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .superpowers\sdd\.pytest-kaomoji-full
```

Expected: 18 张关键帧通过；三动作各 `180 Chinese + 20 kaomoji`；pytest 0 failed，passed 数不少于原基线 142。

- [ ] **Step 2: 用 Windows PowerShell 5.1 完整构建**

```powershell
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

Expected: 只生成 `dist\桌面宠物-6帧猫耳颜文字版.exe`；归档验证通过；无第二个 EXE。

- [ ] **Step 3: 执行 EXE 启动与资源探针**

启动 EXE，确认进程保持运行、单实例锁正常；通过探针记录三套字体均从 `_MEIPASS/assets/fonts/...` 打开。若字体缺失或损坏，程序必须明确失败，不能出现系统字体或方框。

- [ ] **Step 4: 在用户可见 Windows 桌面完成 9 次真实点击**

用户实际双击最终 EXE，连续有效点击角色 9 次，记录动作严格为：

```text
jump, squash, shake, jump, squash, shake, jump, squash, shake
```

逐次核对气泡内容属于对应动作的 200 条库；同一动作相邻两次不得重复。该步骤必须由用户交互桌面完成，进程内 Tk 事件测试不能替代。

- [ ] **Step 5: 完成四边位置和截图 QA**

把角色分别拖到工作区上、下、左、右边缘，每处触发一次；确认气泡不遮挡角色、不超屏、尾巴指向角色。保存真实桌面截图为 `qa/cat-ear-bubble-runtime.png`，并在 `qa/kaomoji-release-report.md` 写明截图只证明该时刻的视觉，不证明随机概率。

- [ ] **Step 6: 复制最终交付物并核对哈希**

使用显式路径复制：

```powershell
Copy-Item -LiteralPath dist\桌面宠物-6帧猫耳颜文字版.exe -Destination 交付\桌面宠物-6帧猫耳颜文字版.exe
Copy-Item -LiteralPath assets\dialogue\phrases.json -Destination 交付\台词库-600句.json
Copy-Item -LiteralPath THIRD_PARTY_NOTICES.txt -Destination 交付\THIRD_PARTY_NOTICES.txt
New-Item -ItemType Directory -Force -Path 交付\字体许可
Copy-Item -LiteralPath assets\fonts\licenses\ZCOOLKuaiLe-OFL-1.1.txt -Destination 交付\字体许可\ZCOOLKuaiLe-OFL-1.1.txt
Copy-Item -LiteralPath assets\fonts\licenses\NotoSans-OFL-1.1.txt -Destination 交付\字体许可\NotoSans-OFL-1.1.txt
Copy-Item -LiteralPath assets\fonts\licenses\NotoSansMath-OFL-1.1.txt -Destination 交付\字体许可\NotoSansMath-OFL-1.1.txt
Get-FileHash -Algorithm SHA256 -LiteralPath 交付\桌面宠物-6帧猫耳颜文字版.exe,交付\台词库-600句.json
```

Expected: JSON SHA-256 为 `829179B422184A92FAA9D164F839D7B8AB0233B08F4E24904961B43EA4CE4CDB`；EXE 字节数和 SHA-256 写入 release report。

- [ ] **Step 7: 最终独立审查与提交**

独立审查范围为上一个发布基线 `a080400..HEAD`，重点检查系统字体回退、每动作 180+20、归档资源、粉边回归和真实 QA 证据。修复所有 Critical/Important 后：

```powershell
git add .superpowers\sdd\progress.md qa 交付
git commit -m "release: deliver six-frame kaomoji desktop pet"
```

Expected: `git status --short` 无输出；最终报告列出 EXE 路径、字节数、SHA-256、测试数和仍需用户确认的任何证据边界。

---

## 计划自审记录

- 规格覆盖：三字体、逐字符 cmap、28/40px、180+20、540 条原中文保留、气泡 Alpha、PyInstaller 归档、9 次点击、四边位置和许可交付均有对应任务。
- 类型一致：后续统一消费 `FontRunResolver`、`TextLayout`、`draw_layout`、`is_kaomoji_phrase` 和 `validate_phrase_rendering`；无第二套测宽实现。
- 数据一致：源 JSON 哈希固定为 `927C...D3B2`，最终哈希固定为 `8291...4CDB`；60 条颜文字已只读验证为全局唯一、6–10 码位、两套字体无缺字、宽度 75–200px。
- 范围一致：不新增动作、音效、联网、设置窗口或 30 帧素材；不修改角色关键帧。

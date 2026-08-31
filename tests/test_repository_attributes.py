from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXED_LF_PATHS = (
    "/assets/fonts/licenses/ZCOOLKuaiLe-OFL-1.1.txt",
    "/assets/fonts/licenses/NotoSans-OFL-1.1.txt",
    "/assets/fonts/licenses/NotoSansMath-OFL-1.1.txt",
    "/assets/rig/v1/source/eye-neutral-v1/authoring.json",
)


def test_fixed_hash_text_sources_are_pinned_to_lf_with_exact_path_rules() -> None:
    attributes = ROOT / ".gitattributes"

    assert attributes.is_file(), "repository .gitattributes is missing"
    assert attributes.read_text(encoding="utf-8").splitlines() == [
        f"{path} text eol=lf" for path in FIXED_LF_PATHS
    ]

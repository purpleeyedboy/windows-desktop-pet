from pathlib import Path


def test_build_validates_archived_keyframe_hashes():
    script = Path("build.ps1").read_text(encoding="utf-8")

    assert "--keyframe-root" in script
    assert r"assets\keyframes" in script


def test_pyinstaller_excludes_offline_image_tooling():
    spec = Path("desktop_pet.spec").read_text(encoding="utf-8")

    assert 'excludes=["numpy", "cv2"]' in spec

from pathlib import Path


def test_build_validates_six_direct_archived_keyframes():
    script = Path("build.ps1").read_text(encoding="utf-8")

    assert "--keyframe-root" in script
    assert r"assets\keyframes" in script
    assert "--frame-count 6" in script
    assert "--keyframe-layout direct" in script


def test_pyinstaller_packages_only_six_frame_keyframes_with_distinct_name():
    spec = Path("desktop_pet.spec").read_text(encoding="utf-8")

    assert '"keyframes"' in spec
    assert '"assets/keyframes"' in spec
    assert '"assets" / "pet"' not in spec
    assert 'name="桌面宠物-6帧无粉边版"' in spec


def test_pyinstaller_excludes_offline_image_tooling():
    spec = Path("desktop_pet.spec").read_text(encoding="utf-8")

    assert 'excludes=["numpy", "cv2"]' in spec

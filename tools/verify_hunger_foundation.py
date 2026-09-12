"""Reject a hunger build if inherited foundation bytes differ from recorded Git blobs."""
from hashlib import sha1, sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    provenance = json.loads((ROOT / "docs/hunger-foundation-provenance.json").read_text("utf-8"))
    if provenance.get("activity_recovery_fix_commit") != "1a18477faa4caa28170e648437d7cb8b39612ac0":
        raise RuntimeError("published activity recovery source is not recorded")
    sources = provenance["files"]
    if not sources:
        raise RuntimeError("foundation source record is empty")
    required = {str(path.relative_to(ROOT)).replace("\\", "/") for path in (ROOT / "src/desktop_pet/foundation").glob("*.py")}
    required.update({"src/desktop_pet/window.py", "src/desktop_pet/animation.py", "src/desktop_pet/assets.py", "src/desktop_pet/eye_runtime.py", "src/desktop_pet/layered_window.py"})
    if not required.issubset(sources):
        raise RuntimeError(f"foundation source files missing: {required - set(sources)}")
    for name, record in sources.items():
        data = (ROOT / name).read_bytes()
        # git checkout may convert text line endings on Windows. Git blob identity
        # always describes canonical LF content in this repository.
        canonical = data.replace(b"\r\n", b"\n")
        blob = sha1(b"blob " + str(len(canonical)).encode() + b"\0" + canonical).hexdigest()
        if blob != record["git_blob"] or sha256(canonical).hexdigest() != record["sha256"]:
            raise RuntimeError(f"inherited foundation file differs from verified source: {name}")
        if len(record["source_commit"]) != 40:
            raise RuntimeError(f"source commit is not recorded: {name}")
    print(f"verified {len(sources)} inherited foundation files against recorded Git blobs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

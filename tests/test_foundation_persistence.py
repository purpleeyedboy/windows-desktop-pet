import json

from desktop_pet.foundation.persistence import AtomicJsonStore


def test_atomic_store_replaces_target_and_round_trips_versioned_payload(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    replaced = []
    store = AtomicJsonStore(path, schema="desktop-pet-core", version=1)
    monkeypatch.setattr(store, "_replace", lambda source, target: (replaced.append((source, target)), source.replace(target))[1])
    store.save({"window": {"x": -100, "y": 20}})
    assert replaced and replaced[0][0].parent == tmp_path
    assert store.load(default={}) == {"window": {"x": -100, "y": 20}}


def test_corrupt_wrong_schema_or_version_safely_returns_fresh_default(tmp_path):
    path = tmp_path / "state.json"
    store = AtomicJsonStore(path, schema="desktop-pet-core", version=1)
    for content in ("not-json", json.dumps({"schema": "wrong", "version": 1, "data": {}}), json.dumps({"schema": "desktop-pet-core", "version": 2, "data": {}})):
        path.write_text(content, encoding="utf-8")
        default = {"safe": True}
        assert store.load(default=default) == default

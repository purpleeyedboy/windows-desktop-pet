from types import SimpleNamespace
from desktop_pet.feed_core.confirmation import TkFeedConfirmation


class Owner:
    def __init__(self):
        self.jobs = []
    def after(self, delay, callback):
        self.jobs.append(callback)
        return len(self.jobs)
    def after_cancel(self, job):
        pass


def accept(dialog, checked=True):
    dialog._callback = lambda accepted: None
    dialog._remember = SimpleNamespace(get=lambda: checked)
    dialog._finish(True)


def test_opt_out_survives_restart_and_avoids_window(tmp_path):
    path = tmp_path / 'feed-preferences.json'
    first = TkFeedConfirmation(Owner(), preference_path=path)
    accept(first)
    owner = Owner()
    reopened = TkFeedConfirmation(owner, preference_path=path)
    results = []
    reopened.show(None, 0, results.append)
    assert results == []  # defer to avoid recursive revalidation
    owner.jobs.pop()()
    assert results == [True]
    assert reopened.window is None


def test_cancel_does_not_save_checked_preference(tmp_path):
    path = tmp_path / 'feed-preferences.json'
    dialog = TkFeedConfirmation(Owner(), preference_path=path)
    dialog._remember = SimpleNamespace(get=lambda: True)
    dialog._finish(False)
    assert not path.exists()


def test_cancel_invalidates_deferred_acceptance(tmp_path):
    owner = Owner()
    dialog = TkFeedConfirmation(owner, preference_path=tmp_path / 'prefs.json')
    accept(dialog)
    results = []
    dialog.show(None, 0, results.append)
    dialog.cancel()
    owner.jobs.pop()()
    assert results == [False]


def test_unchecked_confirmation_does_not_save(tmp_path):
    path = tmp_path / 'prefs.json'
    dialog = TkFeedConfirmation(Owner(), preference_path=path)
    accept(dialog, False)
    assert not path.exists()


def test_corrupt_preference_requires_confirmation(tmp_path):
    path = tmp_path / 'prefs.json'
    path.write_text('broken', encoding='utf-8')
    dialog = TkFeedConfirmation(Owner(), preference_path=path)
    assert dialog._skip_confirmation is False


def test_opt_out_still_revalidates_identity_before_prepared(tmp_path):
    from dataclasses import replace
    from runpy import run_path
    from pathlib import Path
    fixtures = run_path(str(Path(__file__).resolve().parents[1] / 'tools/check_feed_business.py'))
    snapshot = fixtures['snapshot']
    changed = replace(snapshot, file_id_128=b'y' * 16)
    snapshots = iter((snapshot, changed))
    identity = SimpleNamespace(inspect=lambda path: next(snapshots))
    owner = Owner()
    dialog = TkFeedConfirmation(owner, preference_path=tmp_path / 'prefs.json')
    accept(dialog)
    state, recycler = fixtures['State'](), fixtures['Recycler']()
    handler = fixtures['FeedBusinessHandler'](identity, dialog, recycler, state,
        fixtures['Activity'](), fixtures['hunger'], fixtures['clock'])
    assert handler.handle_drop(SimpleNamespace(paths=(snapshot.canonical_path,)))
    owner.jobs.pop()()
    assert state.events == []
    assert not hasattr(recycler, 'prepared')

from datetime import UTC, datetime

from hermes_skilleval import storage


def test_ensure_dir_creates_and_returns_path(tmp_path):
    directory = tmp_path / "nested" / "runs"

    result = storage.ensure_dir(directory)

    assert result == directory
    assert result.is_dir()


def test_timestamped_run_dir_adds_suffix_for_same_second_collision(tmp_path, monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 5, 21, 12, 34, 56, tzinfo=UTC)

    monkeypatch.setattr(storage, "datetime", FixedDateTime)

    first = storage.timestamped_run_dir(tmp_path)
    second = storage.timestamped_run_dir(tmp_path)

    assert first == tmp_path / "20260521T123456Z"
    assert second == tmp_path / "20260521T123456Z-001"
    assert first.is_dir()
    assert second.is_dir()

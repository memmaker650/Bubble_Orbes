from orbes.db import Database


def test_scores_sorted_and_limited():
    db = Database(":memory:")
    for name, score in [("a", 50), ("b", 300), ("c", 120)]:
        db.add_score(name, score, 1)
    top = db.top_scores(2)
    assert [r["player"] for r in top] == ["b", "c"]


def test_settings_roundtrip_and_overwrite():
    db = Database(":memory:")
    assert db.get_setting("x", "d") == "d"
    db.set_setting("x", 1)
    db.set_setting("x", 2)
    assert db.get_setting("x") == "2"


def test_unlock_level_only_increases_and_is_capped():
    db = Database(":memory:")
    assert db.unlocked_level() == 1
    db.unlock_level(3, max_level=3)
    db.unlock_level(2, max_level=3)
    assert db.unlocked_level() == 3
    db.unlock_level(9, max_level=3)
    assert db.unlocked_level() == 3


def test_persists_on_disk(tmp_path):
    path = tmp_path / "orbes.db"
    db = Database(path)
    db.add_score("z", 10, 1)
    db.close()
    assert Database(path).top_scores()[0]["player"] == "z"

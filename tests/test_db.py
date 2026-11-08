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


def test_persists_on_disk(tmp_path):
    path = tmp_path / "orbes.db"
    db = Database(path)
    db.add_score("z", 10, 1)
    db.close()
    assert Database(path).top_scores()[0]["player"] == "z"


def test_scores_store_difficulty():
    db = Database(":memory:")
    db.add_score("a", 300, 2, "hard")
    db.add_score("b", 200, 1, "easy")
    db.add_score("c", 100, 1)                 # sin dificultad (partidas antiguas)
    rows = db.top_scores()
    assert [(r["player"], r["difficulty"]) for r in rows] == [("a", "hard"), ("b", "easy"), ("c", None)]


def test_migration_keeps_old_scores_without_difficulty(tmp_path):
    import sqlite3
    from orbes.db import SCHEMA_V1, SCHEMA_V2
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_V1)
    conn.executescript(SCHEMA_V2)
    conn.execute("INSERT INTO scores (player, score, level) VALUES ('viejo', 999, 3)")
    conn.commit()
    conn.close()
    db = Database(path)
    assert db.conn.execute("PRAGMA user_version").fetchone()[0] == 3
    row = db.top_scores()[0]
    assert row["player"] == "viejo" and row["score"] == 999 and row["difficulty"] is None

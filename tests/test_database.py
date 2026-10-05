import database as db


def test_database_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "findit.db")
    db.init_db()

    detections = [{
        "object_name": "laptop",
        "confidence": 0.95,
        "x1": 10.0,
        "y1": 20.0,
        "x2": 100.0,
        "y2": 120.0,
    }]

    scan_id = db.create_scan("scan.jpg", "Study Desk", detections)
    scan = db.get_scan(scan_id)
    assert scan["location"] == "Study Desk"

    rows = db.find_sightings("laptop")
    assert len(rows) == 1
    assert rows[0]["object_name"] == "laptop"
    assert rows[0]["location"] == "Study Desk"

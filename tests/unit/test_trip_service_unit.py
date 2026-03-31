from app.services import trip_service


class _FakeCursor:
    def __init__(self):
        self._fetchone_calls = 0
        self._fetchall_calls = 0

    def execute(self, _query, _params=None):
        return None

    def fetchone(self):
        self._fetchone_calls += 1
        if self._fetchone_calls == 1:
            return ("m-1", "boat-1", "departure", [])
        return None

    def fetchall(self):
        self._fetchall_calls += 1
        if self._fetchall_calls == 1:
            return [
                ("c-1", "Crew 1", "1111", "9999999999", True, "crop-1"),
                ("c-2", None, None, None, None, None),
            ]
        return []

    def close(self):
        return None


class _FakeConnection:
    def __init__(self):
        self._cursor = _FakeCursor()

    def cursor(self):
        return self._cursor

    def close(self):
        return None


def test_get_arrival_crew_reference_bundle_keeps_attached_crew_without_active_profile(monkeypatch):
    monkeypatch.setattr(trip_service, "get_db_connection", lambda: _FakeConnection())

    bundle = trip_service.get_arrival_crew_reference_bundle("m-1")

    assert bundle is not None
    assert bundle["movement_id"] == "m-1"
    assert bundle["boat_id"] == "boat-1"
    assert [crew["id"] for crew in bundle["departure_crew"]] == ["c-1", "c-2"]
    assert bundle["departure_crew"][1]["name"] is None
    assert bundle["departure_crew"][1]["crop_id"] is None


class _HistoryCursor:
    def __init__(self):
        self.executed_queries = []

    def execute(self, query, params=None):
        self.executed_queries.append((query, params))

    def fetchall(self):
        return []

    def close(self):
        return None


class _HistoryConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def close(self):
        return None


def test_get_movement_history_departure_requires_inventory(monkeypatch):
    cursor = _HistoryCursor()
    monkeypatch.setattr(trip_service, "get_db_connection", lambda: _HistoryConnection(cursor))

    rows = trip_service.get_movement_history("departure", "today", officer_user_id="off-1")

    assert rows == []
    assert cursor.executed_queries
    query, params = cursor.executed_queries[0]
    assert "FROM boat_movement_inventory bmi" in query
    assert "m.movement_type = 'departure'" in query
    assert params is not None


class _DashboardCursor:
    def __init__(self):
        self.executed_queries = []

    def execute(self, query, params=None):
        self.executed_queries.append((query, params))

    def fetchone(self):
        return (0, 0, 0, 0)

    def close(self):
        return None


class _DashboardConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def close(self):
        return None


def test_get_dashboard_today_counts_departures_require_inventory(monkeypatch):
    cursor = _DashboardCursor()
    monkeypatch.setattr(trip_service, "get_db_connection", lambda: _DashboardConnection(cursor))
    trip_service._dashboard_counts_cache.clear()

    result = trip_service.get_dashboard_today_counts(officer_user_id="off-1")

    assert result["departures"] == 0
    assert cursor.executed_queries
    query, params = cursor.executed_queries[0]
    assert "FROM boat_movement_inventory bmi" in query
    assert "FROM boat_movements m" in query
    assert params is not None


class _ArrivalDiscrepancyCursor:
    def __init__(self):
        self._fetchone_calls = 0
        self._fetchall_calls = 0

    def execute(self, _query, _params=None):
        return None

    def fetchone(self):
        self._fetchone_calls += 1
        if self._fetchone_calls == 1:
            return (
                {
                    "movement_id": "mov-1",
                    "missing_crew_ids": ["c-2"],
                    "unidentified_crew_ids": ["u-1"],
                    "report_missing_person": True,
                    "notes": "One crew missing",
                },
            )
        return None

    def fetchall(self):
        self._fetchall_calls += 1
        if self._fetchall_calls == 1:
            return [("u-1", "/uploads/crew-crops/u-1.png")]
        return []

    def close(self):
        return None


class _ArrivalDiscrepancyConnection:
    def __init__(self):
        self._cursor = _ArrivalDiscrepancyCursor()

    def cursor(self):
        return self._cursor

    def close(self):
        return None


def test_get_arrival_crew_discrepancy_returns_missing_and_unidentified(monkeypatch):
    monkeypatch.setattr(trip_service, "get_db_connection", lambda: _ArrivalDiscrepancyConnection())

    result = trip_service.get_arrival_crew_discrepancy("mov-1")

    assert result["missing_crew_ids"] == ["c-2"]
    assert result["unidentified_crew"] == [{"id": "u-1", "crop_image_url": "/uploads/crew-crops/u-1.png"}]
    assert result["report_missing_person"] is True
    assert result["notes"] == "One crew missing"

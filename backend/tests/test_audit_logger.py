import json

from backend.audit_logger import safe_truncate, write_audit


class TestSafeTruncate:
    def test_none_returns_none(self):
        assert safe_truncate(None) is None

    def test_empty_string_unchanged(self):
        assert safe_truncate("") == ""

    def test_under_limit_unchanged(self):
        assert safe_truncate("hello", limit=10) == "hello"

    def test_exactly_at_limit_unchanged(self):
        s = "a" * 10
        assert safe_truncate(s, limit=10) == s

    def test_over_limit_truncated_with_ellipsis(self):
        s = "a" * 20
        result = safe_truncate(s, limit=10)
        assert result == "a" * 10 + "…"

    def test_default_limit_is_500(self):
        short = "x" * 499
        assert safe_truncate(short) == short

        long = "x" * 501
        result = safe_truncate(long)
        assert result.endswith("…")
        assert len(result) == 501  # 500 chars + ellipsis


class TestWriteAudit:
    def test_writes_valid_json_line(self, tmp_path, monkeypatch):
        log_file = tmp_path / "audit.jsonl"
        monkeypatch.setattr("backend.audit_logger.AUDIT_LOG_PATH", log_file)

        write_audit({"event": "login", "actor": "tester"})

        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["event"] == "login"
        assert data["actor"] == "tester"
        assert "ts" in data

    def test_auto_adds_timestamp(self, tmp_path, monkeypatch):
        log_file = tmp_path / "audit.jsonl"
        monkeypatch.setattr("backend.audit_logger.AUDIT_LOG_PATH", log_file)

        write_audit({"event": "query"})
        data = json.loads(log_file.read_text())
        assert isinstance(data["ts"], int)
        assert data["ts"] > 0

    def test_does_not_override_existing_timestamp(self, tmp_path, monkeypatch):
        log_file = tmp_path / "audit.jsonl"
        monkeypatch.setattr("backend.audit_logger.AUDIT_LOG_PATH", log_file)

        write_audit({"event": "x", "ts": 9999})
        data = json.loads(log_file.read_text())
        assert data["ts"] == 9999

    def test_appends_multiple_events(self, tmp_path, monkeypatch):
        log_file = tmp_path / "audit.jsonl"
        monkeypatch.setattr("backend.audit_logger.AUDIT_LOG_PATH", log_file)

        write_audit({"event": "first"})
        write_audit({"event": "second"})
        write_audit({"event": "third"})

        lines = [ln for ln in log_file.read_text().strip().split("\n") if ln]
        assert len(lines) == 3
        events = [json.loads(ln)["event"] for ln in lines]
        assert events == ["first", "second", "third"]

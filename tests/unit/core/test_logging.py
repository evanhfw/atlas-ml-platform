import json
import logging
import sys
from datetime import datetime
from types import TracebackType
from uuid import uuid4

import pytest

from atlas_ml_platform.config import Settings
from atlas_ml_platform.core.logging import (
    JsonFormatter,
    configure_logging,
    request_id_var,
)

TEST_DATABASE_URL = (
    "postgresql+asyncpg://atlas:atlas_dev_password@localhost:5432/atlas_test"
)


@pytest.fixture
def formatter() -> JsonFormatter:
    return JsonFormatter(service="atlas-test", environment="testing")


def _record(
    *,
    msg: str = "event",
    args: tuple[object, ...] = (),
    exc_info: tuple[type[BaseException], BaseException, TracebackType | None]
    | tuple[None, None, None]
    | None = None,
    level: int = logging.INFO,
) -> logging.LogRecord:
    return logging.LogRecord(
        name="tests.unit.core.logging",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=exc_info,
    )


def test_formatter_emits_json_envelope_with_service_and_environment(
    formatter: JsonFormatter,
) -> None:
    payload = json.loads(formatter.format(_record(msg="inference_completed")))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "tests.unit.core.logging"
    assert payload["message"] == "inference_completed"
    assert payload["service"] == "atlas-test"
    assert payload["environment"] == "testing"
    assert datetime.fromisoformat(payload["timestamp"]).tzinfo is not None


def test_formatter_merges_request_context_and_structured_extras(
    formatter: JsonFormatter,
) -> None:
    request_id = uuid4()
    token = request_id_var.set(request_id)
    try:
        record = _record(msg="request_failed")
        record.method = "GET"
        record.path = "/api/v1/models"
        record.status_code = 404
        record.duration_ms = 12.5
        record.error_code = "model_not_found"
        record.error_type = "ModelNotFound"
        payload = json.loads(formatter.format(record))
    finally:
        request_id_var.reset(token)

    assert payload["request_id"] == str(request_id)
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/v1/models"
    assert payload["status_code"] == 404
    assert payload["duration_ms"] == 12.5
    assert payload["error_code"] == "model_not_found"
    assert payload["error_type"] == "ModelNotFound"


def test_formatter_includes_traceback_only_when_exc_info_is_present(
    formatter: JsonFormatter,
) -> None:
    plain = json.loads(formatter.format(_record(msg="request_completed")))
    assert "exception" not in plain

    try:
        raise ValueError("do-not-leak-detail")
    except ValueError:
        exc_info = sys.exc_info()

    failed = json.loads(
        formatter.format(
            _record(msg="request_failed", exc_info=exc_info, level=logging.ERROR)
        )
    )

    assert "Traceback (most recent call last)" in failed["exception"]
    assert "ValueError: do-not-leak-detail" in failed["exception"]


def test_formatter_renders_message_arguments_instead_of_raw_template(
    formatter: JsonFormatter,
) -> None:
    emitted = formatter.format(_record(msg="artifact %s ready", args=("model.joblib",)))
    payload = json.loads(emitted)

    assert payload["message"] == "artifact model.joblib ready"
    assert "%s" not in emitted


def test_configure_logging_emits_one_line_per_record_when_called_twice(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        APP_NAME="atlas-dedupe-test",
        APP_ENV="testing",
        DATABASE_URL=TEST_DATABASE_URL,
        LOG_LEVEL="INFO",
    )
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    try:
        configure_logging(settings)
        configure_logging(settings)

        logging.getLogger("tests.unit.core.dedupe").warning("only_once")
        lines = [
            line for line in capsys.readouterr().out.splitlines() if "only_once" in line
        ]
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)

    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["message"] == "only_once"
    assert payload["service"] == "atlas-dedupe-test"

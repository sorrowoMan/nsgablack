import json
import logging

from nsgablack.utils.engineering.logging_config import JsonFormatter, configure_logging


def test_json_formatter_fields():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello",
        args=(),
        exc_info=None,
    )
    formatted = JsonFormatter().format(record)
    payload = json.loads(formatted)
    assert payload["level"] == "INFO"
    assert payload["name"] == "test"
    assert payload["message"] == "hello"


def test_configure_logging_json():
    logger = configure_logging(level="DEBUG", json_format=True, force=True)
    assert logger.level == logging.DEBUG
    assert any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers)

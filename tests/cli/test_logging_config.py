"""Unit tests for guffin.cli.logging_config."""

import logging

from guffin.cli.logging_config import _RecordSuppressionFilter


def _record(logger_name: str, message: str) -> logging.LogRecord:
    """Build a WARNING-level LogRecord for *logger_name* carrying *message*."""
    return logging.LogRecord(
        name=logger_name, level=logging.WARNING, pathname="x.py", lineno=1, msg=message, args=None, exc_info=None
    )


class TestRecordSuppressionFilter:
    """_RecordSuppressionFilter drops only the (logger prefix, message) pairs it lists."""

    def test_pypdf_wrong_pointing_object_is_dropped(self) -> None:
        """The pypdf malformed-xref recovery warning is suppressed."""
        suppression_filter = _RecordSuppressionFilter()
        record = _record("pypdf._reader", "Ignoring wrong pointing object 39 0 (offset 0)")
        assert suppression_filter.filter(record) is False

    def test_other_pypdf_warnings_pass(self) -> None:
        """A different pypdf warning is not suppressed."""
        suppression_filter = _RecordSuppressionFilter()
        record = _record("pypdf._reader", "incorrect startxref pointer(1)")
        assert suppression_filter.filter(record) is True

    def test_same_message_from_other_logger_passes(self) -> None:
        """The suppression is scoped to the pypdf loggers, not the message alone."""
        suppression_filter = _RecordSuppressionFilter()
        record = _record("guffin.render.pdf_rendering", "Ignoring wrong pointing object 39 0 (offset 0)")
        assert suppression_filter.filter(record) is True

    def test_prefix_match_requires_dot_boundary(self) -> None:
        """A logger merely sharing the prefix text (e.g. 'pypdfx') is not matched."""
        suppression_filter = _RecordSuppressionFilter()
        record = _record("pypdfx", "Ignoring wrong pointing object 39 0 (offset 0)")
        assert suppression_filter.filter(record) is True

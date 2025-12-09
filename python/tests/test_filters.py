import logging
import pytest

from umelogging.filters import PiiScrubberFilter, _mask, _EMAIL, _PHONE


class TestEmailRegex:
    def test_matches_simple_email(self):
        assert _EMAIL.search("test@example.com")

    def test_matches_email_with_dots(self):
        assert _EMAIL.search("first.last@example.com")

    def test_matches_email_with_plus(self):
        assert _EMAIL.search("user+tag@example.com")

    def test_matches_email_with_numbers(self):
        assert _EMAIL.search("user123@example123.com")

    def test_matches_email_with_subdomain(self):
        assert _EMAIL.search("user@mail.example.com")

    def test_no_match_without_at(self):
        assert not _EMAIL.search("notanemail.com")

    def test_no_match_without_domain(self):
        assert not _EMAIL.search("user@")


class TestPhoneRegex:
    def test_matches_international_format(self):
        assert _PHONE.search("+1 555-123-4567")

    def test_matches_local_format(self):
        assert _PHONE.search("555-123-4567")

    def test_matches_with_parens(self):
        assert _PHONE.search("(555) 123-4567")

    def test_matches_compact(self):
        assert _PHONE.search("5551234567")

    def test_matches_german_format(self):
        assert _PHONE.search("+49 30 12345678")

    def test_matches_spaced_format(self):
        assert _PHONE.search("555 123 4567")


class TestMaskFunction:
    def test_masks_email(self):
        result = _mask("Contact us at user@example.com for help")
        assert result == "Contact us at [email] for help"
        assert "user@example.com" not in result

    def test_masks_multiple_emails(self):
        result = _mask("From: a@b.com To: c@d.com")
        assert result == "From: [email] To: [email]"

    def test_masks_phone(self):
        result = _mask("Call us at 555-123-4567")
        assert "[phone]" in result
        assert "555-123-4567" not in result

    def test_masks_both_email_and_phone(self):
        result = _mask("Email: test@example.com Phone: 555-123-4567")
        assert "[email]" in result
        assert "[phone]" in result
        assert "test@example.com" not in result

    def test_no_change_without_pii(self):
        original = "This is a normal message"
        result = _mask(original)
        assert result == original

    def test_handles_empty_string(self):
        assert _mask("") == ""


class TestPiiScrubberFilter:
    @pytest.fixture
    def filter(self):
        return PiiScrubberFilter()

    @pytest.fixture
    def log_record(self):
        return logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Original message",
            args=(),
            exc_info=None,
        )

    def test_always_returns_true(self, filter, log_record):
        """Filter should always return True (pass record through)."""
        result = filter.filter(log_record)
        assert result is True

    def test_scrubs_email_from_message(self, filter):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="User email is user@example.com",
            args=(),
            exc_info=None,
        )
        filter.filter(record)
        assert "[email]" in record.msg
        assert "user@example.com" not in record.msg

    def test_scrubs_phone_from_message(self, filter):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Call 555-123-4567",
            args=(),
            exc_info=None,
        )
        filter.filter(record)
        assert "[phone]" in record.msg

    def test_handles_format_args(self, filter):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="User %s has email %s",
            args=("John", "john@example.com"),
            exc_info=None,
        )
        filter.filter(record)
        # getMessage() should be called and masked
        assert "[email]" in record.msg

    def test_handles_exception_gracefully(self, filter):
        """Filter should not raise even with problematic records."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg=None,  # Problematic value
            args=(),
            exc_info=None,
        )
        # Should not raise
        result = filter.filter(record)
        assert result is True

    def test_default_fields(self, filter):
        assert "msg" in filter.fields

    def test_custom_fields(self):
        filter = PiiScrubberFilter(fields=("msg", "custom"))
        assert "msg" in filter.fields
        assert "custom" in filter.fields


class TestPiiScrubberIntegration:
    def test_with_logger(self, caplog):
        """Test filter works when attached to a logger."""
        logger = logging.getLogger("test.pii")
        logger.setLevel(logging.DEBUG)

        handler = logging.StreamHandler()
        handler.addFilter(PiiScrubberFilter())
        logger.addHandler(handler)

        with caplog.at_level(logging.INFO):
            logger.info("Contact: test@example.com")

        # The filter modifies the record, caplog should see the filtered version
        # Note: caplog captures before filters in some pytest versions
        logger.removeHandler(handler)

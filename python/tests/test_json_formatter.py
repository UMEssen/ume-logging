import unittest
import logging
from formatter import JsonFormatter  # Replace with actual import path

class TestJsonFormatter(unittest.TestCase):

    def setUp(self):
        self.formatter = JsonFormatter(static_fields={"app": "test_app"})

    def test_format(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test_path",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        formatted = self.formatter.format(record)
        self.assertIn("test_app", formatted)
        self.assertIn("Test message", formatted)

if __name__ == "__main__":
    unittest.main()

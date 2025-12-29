"""
Tests for helper utilities.

Tests:
- Error formatting
- Text truncation
- Agent response handling
"""


class TestHelpers:
    """Tests for helper functions."""

    def test_format_error(self) -> None:
        """Test that format_error formats exceptions correctly."""
        from kube_medic.utils.helpers import format_error

        error = ValueError("Something went wrong")
        result = format_error(error)

        assert "ValueError" in result
        assert "Something went wrong" in result
        assert "❌" in result

    def test_format_error_with_special_chars(self) -> None:
        """Test error formatting with special characters."""
        from kube_medic.utils.helpers import format_error

        error = RuntimeError("Error: Connection refused (localhost:9090)")
        result = format_error(error)

        assert "RuntimeError" in result
        assert "Connection refused" in result

    def test_truncate_text_short(self) -> None:
        """Test that short text is not truncated."""
        from kube_medic.utils.helpers import truncate_text

        text = "Hello, world!"
        result = truncate_text(text, max_length=100)

        assert result == text
        assert "..." not in result

    def test_truncate_text_long(self) -> None:
        """Test that long text is truncated."""
        from kube_medic.utils.helpers import truncate_text

        text = "A" * 100
        result = truncate_text(text, max_length=20)

        assert len(result) == 23  # 20 + "..."
        assert result.endswith("...")
        assert result.startswith("A" * 20)

    def test_truncate_text_exact_length(self) -> None:
        """Test text exactly at max length."""
        from kube_medic.utils.helpers import truncate_text

        text = "A" * 50
        result = truncate_text(text, max_length=50)

        assert result == text
        assert "..." not in result

    def test_truncate_text_with_newlines(self) -> None:
        """Test truncation of text with newlines."""
        from kube_medic.utils.helpers import truncate_text

        text = "Line 1\nLine 2\nLine 3\n" * 10
        result = truncate_text(text, max_length=30)

        assert len(result) == 33  # 30 + "..."
        assert result.endswith("...")

    def test_truncate_text_using_config_default(self) -> None:
        """Test that truncate_text uses config default when max_length=None."""
        from kube_medic.utils.helpers import truncate_text
        from unittest.mock import patch

        text = "X" * 1000

        with patch("kube_medic.utils.helpers.get_settings") as mock_settings:
            mock_settings.return_value.text_truncate_max_length = 100
            result = truncate_text(text, max_length=None)

            assert len(result) == 103  # 100 + "..."
            assert result.endswith("...")


"""
Tests for email tools.

Tests:
- send_email tool with structured template
- Email templates
- Configuration validation
- Error handling
"""

from unittest.mock import MagicMock, patch

import pytest


class TestEmailTemplates:
    """Tests for email templates."""

    def test_subject_template_has_placeholder(self) -> None:
        """Test that subject template has summary placeholder."""
        from kube_medic.tools.email import EMAIL_SUBJECT_TEMPLATE

        assert "{summary}" in EMAIL_SUBJECT_TEMPLATE
        assert "[KubeMedic]" in EMAIL_SUBJECT_TEMPLATE

    def test_html_template_has_all_placeholders(self) -> None:
        """Test that HTML template has all required placeholders."""
        from kube_medic.tools.email import EMAIL_BODY_HTML

        assert "{summary}" in EMAIL_BODY_HTML
        assert "{root_cause}" in EMAIL_BODY_HTML
        assert "{evidence}" in EMAIL_BODY_HTML
        assert "{recommended_fix}" in EMAIL_BODY_HTML

    def test_html_template_has_section_headers(self) -> None:
        """Test that HTML template has proper section headers."""
        from kube_medic.tools.email import EMAIL_BODY_HTML

        assert "Summary" in EMAIL_BODY_HTML
        assert "Root Cause" in EMAIL_BODY_HTML
        assert "Evidence" in EMAIL_BODY_HTML
        assert "Recommended Fix" in EMAIL_BODY_HTML

    def test_subject_template_formats_correctly(self) -> None:
        """Test that subject template formats correctly."""
        from kube_medic.tools.email import EMAIL_SUBJECT_TEMPLATE

        result = EMAIL_SUBJECT_TEMPLATE.format(summary="High CPU Alert")
        assert result == "[KubeMedic] High CPU Alert"


class TestSendEmailTool:
    """Tests for send_email tool."""

    @patch("kube_medic.tools.email.smtplib.SMTP")
    @patch("kube_medic.tools.email.get_settings")
    def test_sends_email_with_template(self, mock_settings, mock_smtp) -> None:
        """Test successful email sending with structured template."""
        from kube_medic.tools.email import send_email

        mock_settings.return_value = MagicMock(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user",
            smtp_password="pass",
            smtp_use_tls=True,
            email_from="sender@example.com",
            email_to="recipient@example.com",
        )

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        result = send_email.invoke({
            "summary": "Pod Crash in Production",
            "root_cause": "Out of memory error",
            "evidence": "Checked pod logs, found OOMKilled",
            "recommended_fix": "kubectl set resources deployment/app --limits=memory=512Mi"
        })

        assert "successfully" in result.lower()
        mock_server.sendmail.assert_called_once()

        # Verify the email content includes both plain and HTML
        call_args = mock_server.sendmail.call_args
        email_content = call_args[0][2]  # Third argument is the message
        assert "[KubeMedic] Pod Crash in Production" in email_content
        assert "Out of memory error" in email_content
        assert "OOMKilled" in email_content

    @patch("kube_medic.tools.email.smtplib.SMTP")
    @patch("kube_medic.tools.email.get_settings")
    def test_sends_html_email(self, mock_settings, mock_smtp) -> None:
        """Test that email is sent as HTML."""
        from kube_medic.tools.email import send_email

        mock_settings.return_value = MagicMock(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="",
            smtp_password="",
            smtp_use_tls=False,
            email_from="sender@example.com",
            email_to="recipient@example.com",
        )

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        result = send_email.invoke({
            "summary": "Test Issue",
            "root_cause": "Test cause",
            "evidence": "Test evidence",
            "recommended_fix": "Test fix"
        })

        assert "successfully" in result.lower()

        # Verify HTML content
        call_args = mock_server.sendmail.call_args
        email_content = call_args[0][2]
        assert "text/html" in email_content

    @patch("kube_medic.tools.email.get_settings")
    def test_fails_when_smtp_host_not_configured(self, mock_settings) -> None:
        """Test error when SMTP host is not configured."""
        from kube_medic.tools.email import send_email

        mock_settings.return_value = MagicMock(
            smtp_host="",
            email_from="sender@example.com",
            email_to="recipient@example.com",
        )

        result = send_email.invoke({
            "summary": "Test",
            "root_cause": "Test",
            "evidence": "Test",
            "recommended_fix": "Test"
        })

        assert "error" in result.lower()
        assert "smtp_host" in result.lower()

    @patch("kube_medic.tools.email.get_settings")
    def test_fails_when_email_from_not_configured(self, mock_settings) -> None:
        """Test error when email_from is not configured."""
        from kube_medic.tools.email import send_email

        mock_settings.return_value = MagicMock(
            smtp_host="smtp.example.com",
            email_from="",
            email_to="recipient@example.com",
        )

        result = send_email.invoke({
            "summary": "Test",
            "root_cause": "Test",
            "evidence": "Test",
            "recommended_fix": "Test"
        })

        assert "error" in result.lower()
        assert "email_from" in result.lower()

    @patch("kube_medic.tools.email.get_settings")
    def test_fails_when_email_to_not_configured(self, mock_settings) -> None:
        """Test error when email_to is not configured."""
        from kube_medic.tools.email import send_email

        mock_settings.return_value = MagicMock(
            smtp_host="smtp.example.com",
            email_from="sender@example.com",
            email_to="",
        )

        result = send_email.invoke({
            "summary": "Test",
            "root_cause": "Test",
            "evidence": "Test",
            "recommended_fix": "Test"
        })

        assert "error" in result.lower()
        assert "email_to" in result.lower()

    @patch("kube_medic.tools.email.smtplib.SMTP")
    @patch("kube_medic.tools.email.get_settings")
    def test_handles_smtp_authentication_error(self, mock_settings, mock_smtp) -> None:
        """Test handling of SMTP authentication error."""
        import smtplib
        from kube_medic.tools.email import send_email

        mock_settings.return_value = MagicMock(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user",
            smtp_password="wrong_pass",
            smtp_use_tls=True,
            email_from="sender@example.com",
            email_to="recipient@example.com",
        )

        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
        mock_smtp.return_value = mock_server

        result = send_email.invoke({
            "summary": "Test",
            "root_cause": "Test",
            "evidence": "Test",
            "recommended_fix": "Test"
        })

        assert "error" in result.lower()
        assert "authentication" in result.lower()

    @patch("kube_medic.tools.email.smtplib.SMTP")
    @patch("kube_medic.tools.email.get_settings")
    def test_handles_smtp_connection_error(self, mock_settings, mock_smtp) -> None:
        """Test handling of SMTP connection error."""
        import smtplib
        from kube_medic.tools.email import send_email

        mock_settings.return_value = MagicMock(
            smtp_host="invalid.host.com",
            smtp_port=587,
            smtp_username="",
            smtp_password="",
            smtp_use_tls=True,
            email_from="sender@example.com",
            email_to="recipient@example.com",
        )

        mock_smtp.side_effect = smtplib.SMTPConnectError(421, b"Connection refused")

        result = send_email.invoke({
            "summary": "Test",
            "root_cause": "Test",
            "evidence": "Test",
            "recommended_fix": "Test"
        })

        assert "error" in result.lower()
        assert "connect" in result.lower()


class TestSendEmailInputSchema:
    """Tests for SendEmailInput schema."""

    def test_schema_has_required_fields(self) -> None:
        """Test that schema has all required fields."""
        from kube_medic.tools.email import SendEmailInput

        schema = SendEmailInput.model_json_schema()
        required = schema.get("required", [])

        assert "summary" in required
        assert "root_cause" in required
        assert "evidence" in required
        assert "recommended_fix" in required
        # to is no longer a parameter - it comes from config
        assert "to" not in required

    def test_schema_field_descriptions(self) -> None:
        """Test that schema fields have descriptions."""
        from kube_medic.tools.email import SendEmailInput

        schema = SendEmailInput.model_json_schema()
        properties = schema.get("properties", {})

        assert "description" in properties["summary"]
        assert "description" in properties["root_cause"]
        assert "description" in properties["evidence"]
        assert "description" in properties["recommended_fix"]


class TestEmailToolsList:
    """Tests for email_tools list."""

    def test_all_tools_in_list(self) -> None:
        """Test that all email tools are in the list."""
        from kube_medic.tools.email import email_tools, send_email

        assert send_email in email_tools

    def test_tools_have_names(self) -> None:
        """Test that tools have proper names."""
        from kube_medic.tools.email import email_tools

        for tool in email_tools:
            assert hasattr(tool, "name")
            assert tool.name is not None

    def test_tools_have_descriptions(self) -> None:
        """Test that tools have descriptions."""
        from kube_medic.tools.email import email_tools

        for tool in email_tools:
            assert hasattr(tool, "description")
            assert tool.description is not None

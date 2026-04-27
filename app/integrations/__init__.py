"""Integrations with external services."""

from app.integrations.telegram import send_message, send_message_safe, edit_message_text, delete_message

__all__ = ["send_message", "send_message_safe", "edit_message_text", "delete_message"]

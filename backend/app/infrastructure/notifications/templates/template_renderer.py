"""
Template renderer for notification content.

Renders Jinja2 templates with notification context at delivery time (consumer-side).
Industry standard approach used by SendGrid, Twilio, Firebase.
"""

import logging
import json
from typing import Dict, Any
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound

logger = logging.getLogger(__name__)


class TemplateRenderer:
    """
    Renders notification templates with Jinja2 at delivery time.

    Consumer-side template rendering (industry standard):
    - SendGrid: Template ID in queue, renders at delivery
    - Firebase: Renders at platform-specific delivery

    Benefits:
    - Template updates affect queued notifications
    - Smaller queue storage
    - Product teams can edit templates without requeuing

    Template Structure:
    backend/templates/notifications/
    ├── email/
    │   ├── achievement.html (full HTML document)
    │   ├── meal_reminder.html
    │   └── daily_summary.html
    ├── sms/
    │   ├── achievement.txt (plain text, will be truncated to 160 chars)
    │   └── meal_reminder.txt
    └── push/
        ├── achievement.json (JSON with title, body, data fields)
        ├── meal_reminder.json
        └── daily_summary.json
    """

    def __init__(self, template_dir: str = None):
        """
        Initialize template renderer.

        Args:
            template_dir: Path to template directory
                         Defaults to backend/templates/notifications
        """
        if template_dir is None:
            # Default: backend/templates/notifications
            # Current file: backend/app/infrastructure/notifications/templates/template_renderer.py
            # Go up to backend/templates/notifications
            current_file = Path(__file__)
            backend_dir = current_file.parent.parent.parent.parent.parent
            template_dir = backend_dir / "templates" / "notifications"

        self.template_dir = Path(template_dir)

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=True,  # Auto-escape HTML for security
            trim_blocks=True,
            lstrip_blocks=True,
        )

        logger.info(f"TemplateRenderer initialized: {self.template_dir}")

    def render(
        self,
        notification_type: str,
        channel: str,
        context: Dict[str, Any],
        user_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Render template for notification.

        Args:
            notification_type: achievement, meal_reminder, daily_summary, etc.
            channel: email, sms, push, whatsapp
            context: Notification context from Template Pattern create()
            user_data: User info (user_name, email, unsubscribe_url, etc.)

        Returns:
            Rendered notification dict:
            {
                "title": str,  # Subject for email, title for push, empty for SMS
                "body": str,   # HTML for email, plain text for SMS, body for push
                "data": dict   # Additional metadata
            }

        Raises:
            TemplateNotFound: If template file doesn't exist
        """
        try:
            # Merge context with user data
            full_context = {**(context or {}), **(user_data or {})}

            # Load template file
            template = self._load_template(notification_type, channel)

            # Render with context
            rendered_content = template.render(**full_context)

            # Post-process based on channel
            result = self._post_process(rendered_content, channel, full_context)

            logger.debug(f"Rendered {notification_type}/{channel}")
            return result

        except TemplateNotFound as e:
            logger.error(f"Template not found: {notification_type}/{channel}")
            raise

        except Exception as e:
            logger.error(
                f"Failed to render {notification_type}/{channel}: {e}",
                exc_info=True
            )
            raise

    def _load_template(self, notification_type: str, channel: str) -> Template:
        """
        Load Jinja2 template file.

        Args:
            notification_type: achievement, meal_reminder, etc.
            channel: email, sms, push, whatsapp

        Returns:
            Jinja2 Template object

        Raises:
            TemplateNotFound: If template file doesn't exist
        """
        # File extensions by channel
        extensions = {
            "email": "html",
            "sms": "txt",
            "push": "json",
            "whatsapp": "txt",
        }
        ext = extensions.get(channel, "txt")

        # Template path: {channel}/{notification_type}.{ext}
        # Example: email/achievement.html
        template_path = f"{channel}/{notification_type}.{ext}"

        return self.env.get_template(template_path)

    def _post_process(
        self,
        rendered_content: str,
        channel: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Post-process rendered content based on channel requirements.

        Args:
            rendered_content: Rendered Jinja2 template string
            channel: email, sms, push, whatsapp
            context: Full context (for metadata)

        Returns:
            {"title": str, "body": str, "data": dict}
        """
        if channel == "email":
            return self._post_process_email(rendered_content)
        elif channel == "sms":
            return self._post_process_sms(rendered_content)
        elif channel == "push":
            return self._post_process_push(rendered_content)
        elif channel == "whatsapp":
            return self._post_process_whatsapp(rendered_content)
        else:
            # Unknown channel - return as-is
            return {"title": "", "body": rendered_content, "data": {}}

    def _post_process_email(self, rendered_html: str) -> Dict[str, Any]:
        """
        Post-process email template.

        Email templates are full HTML documents.
        Extract title from <title> tag if present.
        """
        # Try to extract title from HTML
        title = "Notification from NutriLens"
        if "<title>" in rendered_html and "</title>" in rendered_html:
            start = rendered_html.find("<title>") + 7
            end = rendered_html.find("</title>")
            title = rendered_html[start:end].strip()

        return {
            "title": title,
            "body": rendered_html,  # Full HTML
            "data": {"content_type": "text/html"}
        }

    def _post_process_sms(self, rendered_text: str) -> Dict[str, Any]:
        """
        Post-process SMS template.

        SMS has 160 character limit (standard).
        Clean whitespace and truncate if needed.
        """
        # Clean extra whitespace
        cleaned = " ".join(rendered_text.split())

        # Truncate to 160 characters
        max_length = 160
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length-3] + "..."
            logger.warning(f"SMS truncated from {len(rendered_text)} to {max_length} chars")

        return {
            "title": "",  # SMS has no title
            "body": cleaned,
            "data": {}
        }

    def _post_process_push(self, rendered_json: str) -> Dict[str, Any]:
        """
        Post-process push notification template.

        Push templates are JSON files with structure:
        {
            "title": "...",
            "body": "...",
            "icon": "...",
            "badge": 1,
            "sound": "...",
            "click_action": "...",
            "data": {...}
        }

        Returns normalized structure with title, body, data.
        """
        try:
            push_obj = json.loads(rendered_json)

            # Extract title and body
            title = push_obj.get("title", "")
            body = push_obj.get("body", "")

            # Include all other fields in data
            data = push_obj.get("data", {})
            # Add push-specific fields to data
            for key in ["icon", "badge", "sound", "click_action"]:
                if key in push_obj:
                    data[key] = push_obj[key]

            return {
                "title": title,
                "body": body,
                "data": data
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse push template JSON: {e}")
            # Fallback to plain text
            return {
                "title": "Notification",
                "body": rendered_json,
                "data": {}
            }

    def _post_process_whatsapp(self, rendered_text: str) -> Dict[str, Any]:
        """
        Post-process WhatsApp template.

        WhatsApp supports rich text with emojis and markdown-like formatting.
        No strict length limit like SMS.
        """
        return {
            "title": "",  # WhatsApp has no separate title
            "body": rendered_text.strip(),
            "data": {}
        }

    def template_exists(self, notification_type: str, channel: str) -> bool:
        """
        Check if template file exists.

        Args:
            notification_type: Type of notification
            channel: Channel type

        Returns:
            True if template file exists, False otherwise
        """
        try:
            self._load_template(notification_type, channel)
            return True
        except TemplateNotFound:
            return False

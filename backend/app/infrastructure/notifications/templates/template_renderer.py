"""
Template renderer for notification content.

Renders Jinja2 templates with notification context at delivery time (consumer-side).
Industry standard approach used by SendGrid, Twilio, Firebase.
"""

import logging
import json
from typing import Dict, Any
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound, select_autoescape

logger = logging.getLogger(__name__)


class TemplateRenderer:

    def __init__(self, template_dir: str = None):

        if template_dir is None:
            current_file = Path(__file__)
            backend_dir = current_file.parent.parent.parent.parent.parent
            template_dir = backend_dir / "templates" / "notifications"

        self.template_dir = Path(template_dir)

        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            # Only HTML-escape .html templates — push (.json) and SMS (.txt)
            # templates carry plain text so escaping &→&amp; is wrong there.
            autoescape=select_autoescape(enabled_extensions=("html",)),
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
        try:

            full_context = {**(context or {}), **(user_data or {})}

 
            template = self._load_template(notification_type, channel)


            rendered_content = template.render(**full_context)

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

        extensions = {
            "email": "html",
            "sms": "txt",
            "push": "json",
            "whatsapp": "txt",
        }
        ext = extensions.get(channel, "txt")

        template_path = f"{channel}/{notification_type}.{ext}"

        return self.env.get_template(template_path)

    def _post_process(
        self,
        rendered_content: str,
        channel: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        
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

        try:
            push_obj = json.loads(rendered_json)

            title = push_obj.get("title", "")
            body = push_obj.get("body", "")

            data = push_obj.get("data", {})

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

            return {
                "title": "Notification",
                "body": rendered_json,
                "data": {}
            }

    def _post_process_whatsapp(self, rendered_text: str) -> Dict[str, Any]:

        return {
            "title": "",  # WhatsApp has no separate title
            "body": rendered_text.strip(),
            "data": {}
        }

    def template_exists(self, notification_type: str, channel: str) -> bool:

        try:
            self._load_template(notification_type, channel)
            return True
        except TemplateNotFound:
            return False

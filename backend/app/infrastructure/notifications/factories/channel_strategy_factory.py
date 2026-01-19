"""
Factory for creating channel strategy instances.

Maps channel_type → Channel class instance.
"""

import logging
from typing import Dict
from ..channels import EmailChannel, SMSChannel, PushChannel, WhatsAppChannel

logger = logging.getLogger(__name__)


class ChannelStrategyFactory:
    """
    Factory for creating channel strategy instances.

    Singleton instances of each channel to reuse connections.

    Usage:
        factory = ChannelStrategyFactory()
        email_channel = factory.get_channel("email")
        result = await email_channel.send(user_email, title, body, data)
    """

    def __init__(self):
        """Initialize factory with channel instances."""
        # Create singleton instances for each channel
        self._channels: Dict[str, any] = {
            "email": EmailChannel(),
            "sms": SMSChannel(),
            "push": PushChannel(),
            "whatsapp": WhatsAppChannel(),
        }

    def get_channel(self, channel_type: str):
        """
        Get channel instance by type.

        Args:
            channel_type: "email", "sms", "push", or "whatsapp"

        Returns:
            Channel instance

        Raises:
            ValueError: If channel_type is not supported
        """
        channel = self._channels.get(channel_type)

        if channel is None:
            raise ValueError(
                f"Unknown channel type: {channel_type}. "
                f"Supported types: {list(self._channels.keys())}"
            )

        return channel

    def get_supported_channels(self) -> list:
        """
        Get list of supported channel types.

        Returns:
            List of channel type strings
        """
        return list(self._channels.keys())

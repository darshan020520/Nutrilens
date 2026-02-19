"""
Factory for creating channel strategy instances.

Maps channel_type → Channel class instance.
"""

import logging
from typing import Dict
from ..channels import EmailChannel, SMSChannel, PushChannel, WhatsAppChannel

logger = logging.getLogger(__name__)


class ChannelStrategyFactory:
    def __init__(self):

        self._channels: Dict[str, any] = {
            "email": EmailChannel(),
            "sms": SMSChannel(),
            "push": PushChannel(),
            "whatsapp": WhatsAppChannel(),
        }

    def get_channel(self, channel_type: str):

        channel = self._channels.get(channel_type)
        if channel is None:
            raise ValueError(
                f"Unknown channel type: {channel_type}. "
                f"Supported types: {list(self._channels.keys())}"
            )

        return channel

    def get_supported_channels(self) -> list:

        return list(self._channels.keys())

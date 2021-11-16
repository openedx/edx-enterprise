"""
Channel level settings (global for all channels).
"""


class ChannelSettingsMixin:
    """
    Mixin for channel settings that apply to all channels.
    Provides common settings for all channels. Each channels is free to override settings at their
    Exporter or Transmitter or Client level, as needed
    """

    # a channel should override this to False if they don't want grade changes to
    # cause retransmission of completion records
    INCLUDE_GRADE_FOR_COMPLETION_AUDIT_CHECK = True

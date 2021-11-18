"""
Channel level settings (global for all channels).
"""


class ChannelSettingsMixin:
    """
    Mixin for channel settings that apply to all channels.
    Provides common settings for all channels. Each channels is free to override settings at their
    Exporter or Transmitter or Client level, as needed

    Important: If you add a setting here, please add a test to cover this default, as well as
    any overrides you add on a per channel basis. See this test for an example:
    tests/test_integrated_channels/test_sap_success_factors/test_transmitters/test_learner_data.py
    """

    # a channel should override this to False if they don't want grade changes to
    # cause retransmission of completion records
    INCLUDE_GRADE_FOR_COMPLETION_AUDIT_CHECK = True

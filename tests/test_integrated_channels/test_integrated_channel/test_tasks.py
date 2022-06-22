"""
Test the Enterprise Integrated Channel tasks and related functions.
"""

import unittest
from unittest.mock import Mock, patch

import ddt
import pytest

from integrated_channels.integrated_channel.tasks import locked

EXPIRY_SECONDS = 100
A_MOCK = Mock()


@locked(expiry_seconds=EXPIRY_SECONDS, lock_name_kwargs=['channel_code', 'channel_pk'])
def a_locked_method(username, channel_code, channel_pk):  # lint-amnesty, pylint: disable=unused-argument
    A_MOCK.subtask()


@locked(expiry_seconds=EXPIRY_SECONDS, lock_name_kwargs=['channel_code', 'channel_pk'])
def a_locked_method_exception(username, channel_code, channel_pk):
    raise Exception('a_locked_method_exception raised an Exception')


@ddt.ddt
class LockedTest(unittest.TestCase):
    """Test class to verify locking of mocked resources"""

    def setUp(self):
        super().setUp()
        A_MOCK.reset_mock()

    @patch('integrated_channels.integrated_channel.tasks.cache.delete')
    @patch('integrated_channels.integrated_channel.tasks.cache.add')
    @ddt.data(True, False)
    def test_locked_method(self, lock_available, add_mock, delete_mock):
        """
        Test that a method gets executed or not based on if a lock can be acquired
        """
        add_mock.return_value = lock_available
        username = 'edx_worker'
        channel_code = 'DEGREED2'
        channel_pk = 10
        a_locked_method(username=username, channel_code=channel_code, channel_pk=channel_pk)
        cache_key = f'a_locked_method-channel_code:{channel_code}-channel_pk:{channel_pk}'
        self.assertEqual(lock_available, A_MOCK.subtask.called)
        if lock_available:
            add_mock.assert_called_once_with(cache_key, "true", EXPIRY_SECONDS)
            delete_mock.assert_called_once()

    @patch('integrated_channels.integrated_channel.tasks.cache.delete')
    @patch('integrated_channels.integrated_channel.tasks.cache.add')
    def test_locked_method_exception(self, add_mock, delete_mock):
        """
        Test that a lock is unlocked when an exception is raised and that the exception is re-raised
        """
        lock_available = True
        add_mock.return_value = lock_available
        username = 'edx_worker'
        channel_code = 'DEGREED2'
        channel_pk = 10
        with pytest.raises(Exception):
            a_locked_method_exception(username=username, channel_code=channel_code, channel_pk=channel_pk)
        cache_key = f'a_locked_method_exception-channel_code:{channel_code}-channel_pk:{channel_pk}'
        add_mock.assert_called_once_with(cache_key, "true", EXPIRY_SECONDS)
        delete_mock.assert_called_once()

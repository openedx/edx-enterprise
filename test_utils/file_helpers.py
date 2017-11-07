# -*- coding: utf-8 -*-
"""
Utility functions for dealing with files in tests.
"""
from __future__ import absolute_import, unicode_literals

import six
import unicodecsv


# pylint: disable=open-builtin
class MakeCsvStreamContextManager(object):
    """
    Context manager that creates a temporary csv file.
    """

    def __init__(self, header, contents):
        """
        Initialize context manager.

        Arguments:
            header (Iterable): Column headers.
            contents (Iterable): CSV contents - each item represents a line.
        """
        self._header = header
        self._contents = contents
        self._csv_stream = None

    def __enter__(self):
        """
        Enter context setting up context variables.
        """
        self._csv_stream = six.BytesIO()

        writer = unicodecsv.writer(self._csv_stream)

        writer.writerow(self._header)
        writer.writerows(self._contents)

        self._csv_stream.seek(0)
        return self._csv_stream

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Leave the context cleaning what needs to be cleaned.
        """
        self._csv_stream.close()
        assert self._csv_stream.closed

"""
Utility functions for dealing with files in tests.
"""

from io import BytesIO

import unicodecsv


class MakeCsvStreamContextManager:
    """
    Context manager that creates a temporary csv file.
    """

    def __init__(self, header, contents, encoding='utf-8'):
        """
        Initialize context manager.

        Arguments:
            header (Iterable): Column headers.
            contents (Iterable): CSV contents - each item represents a line.
            encoding (String): Default Encoding.
        """
        self._header = header
        self._contents = contents
        self._encoding = encoding
        self._csv_stream = None

    def __enter__(self):
        """
        Enter context setting up context variables.
        """
        self._csv_stream = BytesIO()

        writer = unicodecsv.writer(self._csv_stream, encoding=self._encoding)
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

"""
Fields for Enterprise API serializers.
"""

import base64
import csv

from rest_framework import serializers


class Base64EmailCSVField(serializers.Field):
    """
    Serializers a Base64 encoded CSV with emails into an array of emails
    """
    def to_internal_value(self, data):
        decoded_email_csv = base64.standard_b64decode(data).decode('utf-8').splitlines()
        email_csv = list(csv.DictReader(decoded_email_csv))
        if email_csv and 'email' not in email_csv[0]:
            raise serializers.ValidationError(
                "The .csv file must have a column of email addresses, "
                "indicated by the heading 'email' in the first row."
            )
        return [email.get('email') for email in email_csv]

    def to_representation(self, value):
        return value

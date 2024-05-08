"""
Utility functions for tests
"""
import math
import random
import string


def generate_emails_and_ids(num_emails):
    """
    Generates random emails with random uuids used primarily to test length constraints
    """
    emails_and_ids = {
        ''.join(random.choices(string.ascii_uppercase + string.digits, k=8)) +
        '@gmail.com': math.floor(random.random() * 1000)
        for _ in range(num_emails)
    }
    return emails_and_ids

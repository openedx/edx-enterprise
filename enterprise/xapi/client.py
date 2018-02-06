"""
X API Client used to send API calls to Learning Record Store.
"""
import os
import base64

import requests


class XAPIClient(object):
    """
    X API Client used to send API calls to Learning Record Store.
    """
    key = ''
    secret = ''
    lrs_url = 'https://cloud.scorm.com/tc/39KFEYSSKZ/sandbox/'

    def __init__(self):
        """
        Get key/secret pair for XAPI.
        """
        if 'lrs_key' not in os.environ or 'lrs_secret' not in os.environ:
            raise Exception(
                'lrs_key and lrs_secret environment variable must be '
                'set with appropriate values for XAPIClient to work properly.'
            )
        self.key = os.environ.get('lrs_key')
        self.secret = os.environ.get('lrs_secret')

    data = {
        "actor": {
            "mbox": "mailto:staff@example.com",
            "name": "Alter Ego",
            "objectType": "Agent"
        },
        "verb": {
            "id": "http://adlnet.gov/expapi/verbs/registered",
            "display": {
                "en-US": "registered"
            }
        },
        "object": {
            "id": "http://adlnet.gov/expapi/activities/course",
            "definition": {
                "name": {
                    "en-US": "Algorithms and Data Structures"
                },
                "description": {
                    "en-US": "This is paragraph 2 of the long course description. Add more paragraphs as needed. Make sure to enclose them in paragraph tags"
                }
            },
            "objectType": "Activity"
        }
    }

    @property
    def statements_url(self):
        return self.lrs_url + "statements/"

    @property
    def authorization_header(self):
        return 'Basic {}'.format(
            base64.b64encode('{key}:{secret}'.format(key=self.key, secret=self.secret).encode()).decode()
        )

    def send_learner_activity_report(self):
        """
        Send learner activity data.
        """
        return requests.post(
            self.statements_url,
            json=self.data,
            headers={'authorization': self.authorization_header, 'X-Experience-API-Version': '1.0.1'}
        )

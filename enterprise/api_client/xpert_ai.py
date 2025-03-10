"""
Xpert client
"""

import json

import requests

from django.conf import settings

CONNECT_TIMOUET_SECONDS = 5
READ_TIMEOUT_SECONDS = 20


def chat_completion(prompt, role):
    """
    Generate response using xpert api.

    Arguments:
        prompt (str): ChatGPT prompt
        role (str): ChatGPT role to assume for the prompt.

    Returns:
        (str): Prompt response from OpenAI.
    """
    headers = {
        'Content-Type': 'application/json',
    }

    body = {
        'messages': [{'role': role, 'content': prompt},],
        'client_id': settings.ENTERPRISE_ANALYSIS_CLIENT_ID,
        'system_message': settings.ENTERPRISE_ANALYSIS_SYSTEM_PROMPT
    }

    response = requests.post(
        settings.CHAT_COMPLETION_API_V2,
        headers=headers,
        data=json.dumps(body),
        timeout=(CONNECT_TIMOUET_SECONDS, READ_TIMEOUT_SECONDS)
    )

    return response.json().get('content')

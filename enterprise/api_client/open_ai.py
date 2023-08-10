"""
OpenAI client
"""

import openai

from django.conf import settings

openai.api_key = settings.OPENAI_API_KEY


def chat_completion(prompt, role, model='gpt-3.5-turbo'):
    """
    Use chatGPT https://api.openai.com/v1/chat/completions endpoint to generate a response.

    Arguments:
        prompt (str): ChatGPT prompt
        role (str): ChatGPT role to assume for the prompt.
        model (str): ChatGPT model to use for the prompt completion.

    Returns:
        (str): Prompt response from OpenAI.
    """
    response = openai.ChatCompletion.create(
        model=model,
        messages=[
            {'role': role, 'content': prompt},
        ]
    )

    return response['choices'][0]['message']['content']

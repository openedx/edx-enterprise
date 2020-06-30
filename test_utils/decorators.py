"""
Decorators helpful for testing.
"""
from functools import wraps

import responses


# pylint: disable=keyword-arg-before-vararg
def mock_api_response(method=None, url=None, body='', adding_headers=None, *responses_args, **responses_kwargs):
    """
    Function to get the decorator that can mock API calls made via requests module.

    Example:
        >>>  @mock_api_response_decorator(
        >>>     responses.GET,
        >>>     'http://example.com/api/v1/users/',
        >>>     json={'count': 2, 'next': None, 'previous': None, 'results': [{'id': 7}, {'id': 19}]}
        >>>     additional_responses=[
        >>>         {
        >>>            "method": responses.GET,
        >>>            "url": 'http://example.com/api/v1/users/7/',
        >>>            "json": {'id': 7, 'name': 'test'}
        >>>         },
        >>>         {
        >>>            "method": responses.GET,
        >>>            "url": 'http://example.com/api/v1/users/19/',
        >>>            "json": {'id': 19, 'name': 'test 2'}
        >>>         }
        >>>     ]
        >>>  )
        >>>  def test_responses():
        >>>      pass
    """
    additional_responses = responses_kwargs.pop('additional_responses', [])

    def mock_api_response_decorator(func):
        """
        Decorator to mock out the API requests.
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            """
            Wrapper function around the original function or method.
            """
            responses.add(
                method=method,
                url=url,
                body=body,
                adding_headers=adding_headers,
                *responses_args,
                **responses_kwargs
            )
            for response in additional_responses:
                responses.add(**response)
            return responses.activate(func)(*args, **kwargs)

        return wrapper

    return mock_api_response_decorator


def mock_api_response_with_callback(
        method, url, callback, match_querystring=False, content_type="text/plain", additional_responses=None
):
    """
    Function to get the decorator that can mock API calls made via a callback function.

    Example:
        >>>  def callback(request):
        >>>     status = 200
        >>>     headers = {'request-id': '728d329e-0e86-11e4-a748-0c84dc037c13'}
        >>>     response = {'count': 2, 'next': None, 'previous': None, 'results': [{'id': 7}, {'id': 19}]}
        >>>     return status, headers, json.dumps(response)
        >>>
        >>>  @mock_api_response_with_callback(
        >>>     responses.GET,
        >>>     'http://example.com/api/v1/users/',
        >>>     callback=callback,
        >>>     match_querystring=True,
        >>>     content_type='application/json'
        >>>     additional_responses=[
        >>>         {
        >>>            "method": responses.GET,
        >>>            "url": 'http://example.com/api/v1/users/7/',
        >>>            "content_type": 'application/json',
        >>>            "match_querystring": True,
        >>>            "callback": callback
        >>>         },
        >>>         {
        >>>            "method": responses.GET,
        >>>            "url": 'http://example.com/api/v1/users/7/',
        >>>            "content_type": 'application/json',
        >>>            "match_querystring": True,
        >>>            "callback": callback
        >>>         },
        >>>     ]
        >>>  )
        >>>  def test_responses():
        >>>      pass
    """
    def mock_api_response_decorator(func):
        """
        Decorator to mock out the API requests.
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            """
            Wrapper function around the original function or method.
            """
            responses.add_callback(
                method=method,
                url=url,
                callback=callback,
                match_querystring=match_querystring,
                content_type=content_type,
            )
            for response in additional_responses or []:
                responses.add_callback(**response)

            return responses.activate(func)(*args, **kwargs)

        return wrapper

    return mock_api_response_decorator

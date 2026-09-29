"""
Stand-ins for the openedx-platform modules that ``enterprise.platform_support`` imports.

edx-enterprise's test environment has no openedx-platform install. Where the code
under test imports a platform symbol lazily -- inside a function body, so that the
class is real by the time an ``except`` clause references it -- patching the
importing module's namespace is not enough: the import statement itself runs during
the test. Registering a stub module in ``sys.modules`` makes that import resolve to
a class the test also holds a reference to, which is what keeps ``except`` and
``pytest.raises`` identity checks meaningful.

Only symbols actually exercised by these tests are stubbed. Anything the platform
provides that the tests never touch is deliberately absent, so a new dependency
shows up as an ``AttributeError`` here rather than passing silently.
"""

import sys
import types
from unittest import mock

ENROLLMENT_ERRORS_MODULE = 'openedx.core.djangoapps.enrollments.errors'
COMPLETION_EXCEPTIONS_MODULE = 'completion.exceptions'
COMPLETION_UTILITIES_MODULE = 'completion.utilities'
BRANDING_API_MODULE = 'lms.djangoapps.branding.api'


class CourseEnrollmentError(Exception):
    """Stand-in for the platform's ``CourseEnrollmentError``."""

    def __init__(self, msg, data=None):
        super().__init__(msg)
        self.data = data


class CourseEnrollmentExistsError(CourseEnrollmentError):
    """Stand-in for the platform's ``CourseEnrollmentExistsError``."""

    def __init__(self, message, enrollment):
        super().__init__(message)
        self.enrollment = enrollment


class CourseEnrollmentNotUpdatableError(CourseEnrollmentError):
    """Stand-in for the platform's ``CourseEnrollmentNotUpdatableError``."""


class CourseEnrollmentDoesNotExist(Exception):
    """Stand-in for ``CourseEnrollment.DoesNotExist``."""


class CourseUserGroup:
    """Stand-in for the platform's ``CourseUserGroup`` model."""

    class DoesNotExist(Exception):
        """Stand-in for the model's ``DoesNotExist``."""


def patch_enrollment_errors():
    """
    Return a patcher registering a stub ``enrollments.errors`` module in ``sys.modules``.

    ``lms_update_or_create_enrollment`` imports these three classes at call time, so
    they must resolve to the same objects the tests raise and assert against.
    """
    module = types.ModuleType(ENROLLMENT_ERRORS_MODULE)
    module.CourseEnrollmentError = CourseEnrollmentError
    module.CourseEnrollmentExistsError = CourseEnrollmentExistsError
    module.CourseEnrollmentNotUpdatableError = CourseEnrollmentNotUpdatableError
    return mock.patch.dict(sys.modules, {ENROLLMENT_ERRORS_MODULE: module})


class UnavailableCompletionData(Exception):
    """Stand-in for the completion app's ``UnavailableCompletionData``."""


def patch_completion(get_key_to_last_completed_block):
    """
    Return a patcher registering stub ``completion`` modules in ``sys.modules``.

    ``is_course_accessed`` imports both of these at call time and distinguishes its two
    outcomes purely by whether ``UnavailableCompletionData`` is raised, so the exception
    class the test raises has to be the one the ``except`` clause sees.
    """
    exceptions = types.ModuleType(COMPLETION_EXCEPTIONS_MODULE)
    exceptions.UnavailableCompletionData = UnavailableCompletionData
    utilities = types.ModuleType(COMPLETION_UTILITIES_MODULE)
    utilities.get_key_to_last_completed_block = get_key_to_last_completed_block
    return mock.patch.dict(sys.modules, {
        COMPLETION_EXCEPTIONS_MODULE: exceptions,
        COMPLETION_UTILITIES_MODULE: utilities,
    })


def patch_privacy_url(url='https://example.com/privacy'):
    """
    Return a patcher registering a stub ``lms.djangoapps.branding.api`` in ``sys.modules``.

    ``get_enterprise_sidebar_context`` imports ``get_privacy_url`` at call time to build
    the welcome message, so the module has to exist for the duration of the test.
    """
    module = types.ModuleType(BRANDING_API_MODULE)
    module.get_privacy_url = mock.MagicMock(return_value=url)
    return mock.patch.dict(sys.modules, {BRANDING_API_MODULE: module})

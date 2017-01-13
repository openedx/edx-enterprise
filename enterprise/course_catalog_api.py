# -*- coding: utf-8 -*-
"""
Utilities to get details from the course catalog API.
"""
from __future__ import absolute_import, unicode_literals

from django.utils.translation import ugettext_lazy as _

from enterprise.utils import MultipleProgramMatchError, NotConnectedToOpenEdX

try:
    from openedx.core.djangoapps.api_admin.utils import course_discovery_api_client
except ImportError:
    course_discovery_api_client = None

try:
    from openedx.core.djangoapps.catalog.models import CatalogIntegration
except ImportError:
    CatalogIntegration = None

try:
    from openedx.core.lib.edx_api_utils import get_edx_api_data
except ImportError:
    get_edx_api_data = None


class CourseCatalogApiClient(object):
    """
    Object builds an API client to make calls to the Catalog API.
    """

    def __init__(self, user):
        """
        Create an Course Catalog API client, authenticated with the API token from Django settings.

        This method retrieves an authenticated API client that can be used
        to access the course catalog API. It raises an exception to be caught at
        a higher level if the package doesn't have OpenEdX resources available.
        """
        if CatalogIntegration is None:
            raise NotConnectedToOpenEdX(
                _('To get a CatalogIntegration object, this package must be installed in an OpenEdX environment.')
            )
        if get_edx_api_data is None:
            raise NotConnectedToOpenEdX(
                _('To parse a catalog API response, this package must be installed in an OpenEdX environment.')
            )
        if course_discovery_api_client is None:
            raise NotConnectedToOpenEdX(
                _('To get a catalog API client, this package must be installed in an OpenEdX environment.')
            )

        self.user = user
        self.client = course_discovery_api_client(user)

    def get_all_catalogs(self):
        """
        Return a list of all course catalogs, including name and ID.

        Returns:
            list: List of catalogs available for the user.
        """
        return self._load_data('catalogs')

    def get_course_run(self, course_run_id):
        """
        Return course_run data, including name, ID and seats.

        Args:
            course_run_id(str): Course run ID (aka Course Key) in string format.

        Returns:
            dict: Course run data provided by Course Catalog API.
        """
        return self._load_data('course_runs', resource_id=course_run_id)

    def get_program_by_title(self, program_title):
        """
        Return single program by name, or None if not found.

        Arguments:
            program_title(str): Program title as seen by students and in Course Catalog Admin

        Returns:
            dict: Program data provided by Course Catalog API
        """
        all_programs = self._load_data('programs')
        matching_programs = [program for program in all_programs if program.get('title') == program_title]
        if len(matching_programs) > 1:
            raise MultipleProgramMatchError(len(matching_programs))
        elif len(matching_programs) == 1:
            return matching_programs[0]
        else:
            return None

    def get_program_by_uuid(self, program_uuid):
        """
        Return single program by UUID, or None if not found.

        Arguments:
            program_uuid(string): Program UUID in string form

        Returns:
            dict: Program data provided by Course Catalog API
        """
        return self._load_data('programs', resource_id=program_uuid)

    def get_common_course_modes(self, course_run_ids):
        """
        Find common course modes for a set of course runs.

        This function essentially returns an intersection of types of seats available
        for each course run.

        Arguments:
            course_run_ids(Iterable[str]): Target Course run IDs.

        Returns:
            set: course modes found in all given course runs

        Examples:
            # run1 has prof and audit, run 2 has the same
            get_common_course_modes(['course-v1:run1', 'course-v1:run2'])
            {'prof', 'audit'}

            # run1 has prof and audit, run 2 has only prof
            get_common_course_modes(['course-v1:run1', 'course-v1:run2'])
            {'prof'}

            # run1 has prof and audit, run 2 honor
            get_common_course_modes(['course-v1:run1', 'course-v1:run2'])
            {}

            # run1 has nothing, run2 has prof
            get_common_course_modes(['course-v1:run1', 'course-v1:run2'])
            {}

            # run1 has prof and audit, run 2 prof, run3 has audit
            get_common_course_modes(['course-v1:run1', 'course-v1:run2', 'course-v1:run3'])
            {}

            # run1 has nothing, run 2 prof, run3 has prof
            get_common_course_modes(['course-v1:run1', 'course-v1:run2', 'course-v1:run3'])
            {}
        """
        available_course_modes = None
        for course_run_id in course_run_ids:
            course_run = self.get_course_run(course_run_id) or {}
            course_run_modes = {seat.get('type') for seat in course_run.get('seats', [])}

            if available_course_modes is None:
                available_course_modes = course_run_modes
            else:
                available_course_modes &= course_run_modes

            if not available_course_modes:
                return available_course_modes

        return available_course_modes

    def _load_data(self, resource, **kwargs):
        """
        Load data from API client.

        Arguments:
            resource(str): type of resource to load

        Returns:
            dict: Deserialized response from Course Catalog API
        """
        return get_edx_api_data(
            CatalogIntegration.current(),
            self.user,
            resource,
            api=self.client,
            **kwargs
        )

# -*- coding: utf-8 -*-
"""
Decorators for Enterprise API views.
"""

from enterprise import utils


class EnterpriseCourseContextSerializerMixin:
    """
    Serializer mixin for serializers that require Enterprise context in course data.
    """

    def update_enterprise_courses(self, enterprise_customer, course_container_key='results', **kwargs):
        """
        This method adds enterprise-specific metadata for each course.

        We are adding following field in all the courses.
            tpa_hint: a string for identifying Identity Provider.
            enterprise_id: the UUID of the enterprise
            **kwargs: any additional data one would like to add on a per-use basis.

        Arguments:
            enterprise_customer: The customer whose data will be used to fill the enterprise context.
            course_container_key: The key used to find the container for courses in the serializer's data dictionary.
        """
        enterprise_context = {
            'tpa_hint': enterprise_customer and enterprise_customer.identity_provider,
            'enterprise_id': enterprise_customer and str(enterprise_customer.uuid),
        }
        enterprise_context.update(**kwargs)

        courses = []
        for course in self.data[course_container_key]:
            courses.append(
                self.update_course(course, enterprise_customer, enterprise_context)
            )
        self.data[course_container_key] = courses

    def update_course(self, course, enterprise_customer, enterprise_context):
        """
        Update course metadata of the given course and return updated course.

        Arguments:
            course (dict): Course Metadata returned by course catalog API
            enterprise_customer (EnterpriseCustomer): enterprise customer instance.
            enterprise_context (dict): Enterprise context to be added to course runs and URLs..

        Returns:
            (dict): Updated course metadata
        """
        course['course_runs'] = self.update_course_runs(
            course_runs=course.get('course_runs') or [],
            enterprise_customer=enterprise_customer,
            enterprise_context=enterprise_context,
        )

        # Update marketing urls in course metadata to include enterprise related info (i.e. our global context).
        marketing_url = course.get('marketing_url')
        if marketing_url:
            query_parameters = dict(enterprise_context, **utils.get_enterprise_utm_context(enterprise_customer))
            course.update({'marketing_url': utils.update_query_parameters(marketing_url, query_parameters)})

        # Finally, add context to the course as a whole.
        course.update(enterprise_context)
        return course

    def update_course_runs(self, course_runs, enterprise_customer, enterprise_context):
        """
        Update Marketing urls in course metadata and return updated course.

        Arguments:
            course_runs (list): List of course runs.
            enterprise_customer (EnterpriseCustomer): enterprise customer instance.
            enterprise_context (dict): The context to inject into URLs.

        Returns:
            (dict): Dictionary containing updated course metadata.
        """
        updated_course_runs = []
        for course_run in course_runs:
            track_selection_url = utils.get_course_track_selection_url(
                course_run=course_run,
                query_parameters=dict(enterprise_context, **utils.get_enterprise_utm_context(enterprise_customer)),
            )

            enrollment_url = enterprise_customer.get_course_run_enrollment_url(course_run.get('key'))

            course_run.update({
                'enrollment_url': enrollment_url,
                'track_selection_url': track_selection_url,
            })

            # Update marketing urls in course metadata to include enterprise related info.
            marketing_url = course_run.get('marketing_url')
            if marketing_url:
                query_parameters = dict(enterprise_context, **utils.get_enterprise_utm_context(enterprise_customer))
                course_run.update({'marketing_url': utils.update_query_parameters(marketing_url, query_parameters)})

            # Add updated course run to the list.
            updated_course_runs.append(course_run)
        return updated_course_runs

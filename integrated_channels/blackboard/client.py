# -*- coding: utf-8 -*-
"""
Client for connecting to Blackboard.
"""
import base64
import copy
import json
import logging
from http import HTTPStatus

import requests
from six.moves.urllib.parse import urljoin  # pylint: disable=import-error

from django.apps import apps

from integrated_channels.blackboard.exporters.content_metadata import BLACKBOARD_COURSE_CONTENT_NAME
from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient
from integrated_channels.utils import refresh_session_if_expired

LOGGER = logging.getLogger(__name__)

# TODO: Refactor candidate (duplication with canvas client)
GRADEBOOK_PATH = '/learn/api/public/v1/courses/{course_id}/gradebook/columns'
ENROLLMENT_PATH = '/learn/api/public/v1/courses/{course_id}/users'
COURSE_PATH = '/learn/api/public/v1/courses'
POST_GRADE_COLUMN_PATH = '/learn/api/public/v2/courses/{course_id}/gradebook/columns'
POST_GRADE_PATH = '/learn/api/public/v2/courses/{course_id}/gradebook/columns/{column_id}/users/{user_id}'
COURSE_V3_PATH = '/learn/api/public/v3/courses/{course_id}'
COURSES_V3_PATH = '/learn/api/public/v3/courses'
COURSE_CONTENT_PATH = '/learn/api/public/v1/courses/{course_id}/contents'
COURSE_CONTENT_CHILDREN_PATH = '/learn/api/public/v1/courses/{course_id}/contents/{content_id}/children'
COURSE_CONTENT_DELETE_PATH = '/learn/api/public/v1/courses/{course_id}/contents/{content_id}'


class BlackboardAPIClient(IntegratedChannelApiClient):
    """
    Client for connecting to Blackboard.
    """

    def __init__(self, enterprise_configuration):
        """
        Instantiate a new client.

        Args:
            enterprise_configuration (BlackboardEnterpriseCustomerConfiguration): An enterprise customers's
            configuration model for connecting with Blackboard
        """
        super().__init__(enterprise_configuration)
        self.config = apps.get_app_config('blackboard')
        self.session = None
        self.expires_at = None

    def create_content_metadata(self, serialized_data):
        """
        Create a course from serialized course metadata
        Returns: (int, str) Status code, Status message
        """
        channel_metadata_item = json.loads(serialized_data.decode('utf-8'))
        BlackboardAPIClient._validate_channel_metadata(channel_metadata_item)
        BlackboardAPIClient._validate_full_course_metadata(channel_metadata_item)

        external_id = channel_metadata_item.get('externalId')

        # blackboard does not support all characters in our courseIds so let's gen a hash instead
        course_id_generated = self.generate_blackboard_course_id(external_id)

        copy_of_channel_metadata = copy.deepcopy(channel_metadata_item)
        copy_of_channel_metadata['course_metadata']['courseId'] = course_id_generated

        LOGGER.info("Creating course with courseId: %s", external_id)
        self._create_session()
        create_url = self.generate_course_create_url()
        response = self._post(create_url, copy_of_channel_metadata['course_metadata'])

        # We wrap error handling in the post, but sanity check for the ID
        bb_course_id = response.json().get('id')
        if not bb_course_id:
            raise ClientError(
                'Something went wrong while creating base course object on Blackboard. Could not retrieve course ID.',
                HTTPStatus.NOT_FOUND.value
            )

        LOGGER.info("Creating content page for Blackboard course with course ID={}".format(external_id))
        course_created_response = self.create_integration_content_for_course(bb_course_id, copy_of_channel_metadata)

        success_body = 'Successfully created Blackboard integration course={bb_course_id} with integration ' \
                       'content={bb_child_id}'.format(
                           bb_course_id=bb_course_id,
                           bb_child_id=course_created_response.json().get('id'),
                       )

        return course_created_response.status_code, success_body

    def update_content_metadata(self, serialized_data):
        """Apply changes to a course if applicable"""
        self._create_session()
        channel_metadata_item = json.loads(serialized_data.decode('utf-8'))

        BlackboardAPIClient._validate_channel_metadata(channel_metadata_item)
        external_id = channel_metadata_item.get('externalId')
        course_id = self._resolve_blackboard_course_id(external_id)
        BlackboardAPIClient._validate_course_id(course_id, external_id)

        LOGGER.info('Updating course with courseId: {}'.format(course_id))
        update_url = self.generate_course_update_url(course_id)
        response = self._patch(update_url, channel_metadata_item.get('course_metadata'))

        bb_course_id = response.json().get('id')

        if not bb_course_id:
            raise ClientError(
                'Unable to update course={} content on Blackboard. Failed to retrieve ID from course update response:'
                '(status_code={}, body={})'.format(external_id, response.status_code, response.text)
            )

        course_contents_url = self.generate_create_course_content_url(bb_course_id)
        course_contents_response = self._get(course_contents_url)

        bb_contents = course_contents_response.json().get('results')
        bb_content_id = None

        for content in bb_contents:
            if content.get('title') == BLACKBOARD_COURSE_CONTENT_NAME:
                bb_content_id = content.get('id')

        if not bb_content_id:
            LOGGER.info('Blackboard integrated course content not found. Generating content.')
        else:
            course_content_delete_url = self.generate_course_content_delete_url(bb_course_id, bb_content_id)
            self._delete(course_content_delete_url)

        course_updated_response = self.update_integration_content_for_course(
            bb_course_id,
            channel_metadata_item,
        )

        return course_updated_response.status_code, course_updated_response.text

    def delete_content_metadata(self, serialized_data):
        """Delete course from blackboard (performs full delete as of now)"""
        self._create_session()
        channel_metadata_item = json.loads(serialized_data.decode("utf-8"))

        BlackboardAPIClient._validate_channel_metadata(channel_metadata_item)
        external_id = channel_metadata_item.get('externalId')
        course_id = self._resolve_blackboard_course_id(external_id)
        BlackboardAPIClient._validate_course_id(course_id, external_id)

        LOGGER.info("Deleting course with courseId: %s", course_id)
        update_url = self.generate_course_update_url(course_id)
        response = self._delete(update_url)
        return response.status_code, response.text

    def create_assessment_reporting(self, user_id, payload):
        """
        Post a learner's subsection assessment grade to the integrated Blackboard course.

        Parameters:
        -----------
            user_id (str): The shared email between a user's edX account and Blackboard account
            payload (str): The (string representation) of the learner data information
        """
        self._create_session()
        learner_data = json.loads(payload)
        external_id = learner_data.get('courseID')

        course_id = self._resolve_blackboard_course_id(external_id)
        BlackboardAPIClient._validate_course_id(course_id, external_id)

        blackboard_user_id = self._get_bb_user_id_from_enrollments(user_id, course_id)
        grade_column_id = self._get_or_create_integrated_grade_column(
            course_id,
            learner_data.get('subsection_name'),
            learner_data.get('subsectionID'),
            learner_data.get('points_possible'),
        )

        grade = learner_data.get('points_earned')
        submission_response = self._submit_grade_to_blackboard(grade, course_id, grade_column_id, blackboard_user_id)

        success_body = 'Successfully posted grade of {grade} to course:{course_id} for user:{user_email}.'.format(
            grade=grade,
            course_id=external_id,
            user_email=user_id,
        )
        return submission_response.status_code, success_body

    def create_course_completion(self, user_id, payload):
        """
        Post a final course grade to the integrated Blackboard course.

        Parameters:
        -----------
            user_id (str): The shared email between a user's edX account and Blackboard account
            payload (str): The (string representation) of the learner data information

        Example payload:
        ---------------
            '{
                courseID: course-edx+555+3T2020,
                score: 0.85,
                completedTimestamp: 1602265162589,
            }'

        """
        self._create_session()
        learner_data = json.loads(payload)
        external_id = learner_data.get('courseID')

        course_id = self._resolve_blackboard_course_id(external_id)
        BlackboardAPIClient._validate_course_id(course_id, external_id)

        blackboard_user_id = self._get_bb_user_id_from_enrollments(user_id, course_id)
        grade_column_id = self._get_or_create_integrated_grade_column(
            course_id,
            "(edX Integration) Final Grade",
            "edx_final_grade"
        )

        grade = learner_data.get('grade') * 100
        submission_response = self._submit_grade_to_blackboard(grade, course_id, grade_column_id, blackboard_user_id)

        success_body = 'Successfully posted grade of {grade} to course:{course_id} for user:{user_email}.'.format(
            grade=grade,
            course_id=external_id,
            user_email=user_id,
        )
        return submission_response.status_code, success_body

    def delete_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        """TODO: course completion deletion is currently not easily supported"""

    @staticmethod
    def _validate_channel_metadata(channel_metadata_item):
        """
        Raise error if external_id invalid or not found
        """
        if 'externalId' not in channel_metadata_item:
            raise ClientError("No externalId found in metadata, please check json data format", 400)

    @staticmethod
    def _validate_course_id(course_id, external_id):
        """
        Raise error if course_id invalid
        """
        if not course_id:
            raise ClientError(
                'Could not find course:{} on Blackboard'.format(external_id),
                HTTPStatus.NOT_FOUND.value
            )

    @staticmethod
    def _validate_full_course_metadata(channel_metadata_items):
        """
        Raise error if course_metadata, course_content_metadata or course_child_content_metadata are invalid.
        """
        metadata_set = set(channel_metadata_items.keys())
        course_metadata_groups = {'course_metadata', 'course_content_metadata', 'course_child_content_metadata'}
        if not course_metadata_groups.issubset(metadata_set):
            raise ClientError(
                'Could not find course metadata group(s):{} necessary to create Blackboard integrated course.'.format(
                    course_metadata_groups - metadata_set
                ),
                HTTPStatus.NOT_FOUND.value
            )

    def _create_session(self):
        """
        Will only create a new session if token expiry has been reached
        """
        self.session, self.expires_at = refresh_session_if_expired(
            self._get_oauth_access_token,
            self.session,
            self.expires_at,
        )

    def _get_oauth_access_token(self):
        """Fetch access token using refresh_token workflow from Blackboard

        Returns:
            access_token (str): the OAuth access token to access the Blackboard server
            expires_in (int): the number of seconds after which token will expire
        Raises:
            HTTPError: If we received a failure response code.
            ClientError: If an unexpected response format was received that we could not parse.
        """

        if not self.enterprise_configuration.refresh_token:
            raise ClientError(
                "Failed to generate oauth access token: Refresh token required.",
                HTTPStatus.INTERNAL_SERVER_ERROR.value
            )

        if (not self.enterprise_configuration.blackboard_base_url
                or not self.config.oauth_token_auth_path):
            raise ClientError(
                "Failed to generate oauth access token: oauth path missing from configuration.",
                HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
        auth_token_url = urljoin(
            self.enterprise_configuration.blackboard_base_url,
            self.config.oauth_token_auth_path,
        )

        auth_token_params = {
            'grant_type': 'refresh_token',
            'refresh_token': self.enterprise_configuration.refresh_token,
        }

        auth_response = requests.post(
            auth_token_url,
            auth_token_params,
            headers={
                'Authorization': self._create_auth_header(),
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
        if auth_response.status_code >= 400:
            raise ClientError(auth_response.text, auth_response.status_code)
        try:
            data = auth_response.json()
            # do not forget to save the new refresh token otherwise subsequent requests will fail
            self.enterprise_configuration.refresh_token = data["refresh_token"]
            self.enterprise_configuration.save()
            return data['access_token'], data["expires_in"]
        except (KeyError, ValueError) as error:
            raise ClientError(auth_response.text, auth_response.status_code) from error

    def _create_auth_header(self):
        """
        auth header in oauth2 token format as required by blackboard doc
        """
        if not self.enterprise_configuration.client_id:
            raise ClientError(
                "Failed to generate oauth access token: Client ID required.",
                HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
        if not self.enterprise_configuration.client_secret:
            raise ClientError(
                "Failed to generate oauth access token: Client secret required.",
                HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
        return 'Basic {}'.format(
            base64.b64encode(u'{key}:{secret}'.format(
                key=self.enterprise_configuration.client_id,
                secret=self.enterprise_configuration.client_secret
            ).encode('utf-8')).decode()
        )

    def generate_blackboard_course_id(self, external_id):
        """
        A course_id suitable for use with blackboard
        """
        return str(abs(hash(external_id)))

    def generate_gradebook_url(self, course_id):
        """
        Blackboard API url helper method.
        Path: Get course gradebook
        """
        return '{base}{path}'.format(
            base=self.enterprise_configuration.blackboard_base_url,
            path=GRADEBOOK_PATH.format(course_id=course_id),
        )

    def generate_enrollment_url(self, course_id):
        """
        Blackboard API url helper method.
        Path: Get course enrollments
        """
        # By including `expand=user` we get access to the user's contact info
        return '{base}{path}?expand=user'.format(
            base=self.enterprise_configuration.blackboard_base_url,
            path=ENROLLMENT_PATH.format(course_id=course_id),
        )

    def generate_course_create_url(self):
        """
        Url to create a course
        """
        return "{base}{path}".format(
            base=self.enterprise_configuration.blackboard_base_url,
            path=COURSES_V3_PATH,
        )

    def generate_course_update_url(self, course_id):
        """
        Url to update one course
        """
        return '{base}{path}'.format(
            base=self.enterprise_configuration.blackboard_base_url,
            path=COURSE_V3_PATH.format(course_id=course_id),
        )

    def generate_courses_url(self):
        """
        Blackboard API url helper method.
        Path: Get course courses
        """
        return '{base}{path}'.format(
            base=self.enterprise_configuration.blackboard_base_url,
            path=COURSE_PATH,
        )

    def generate_create_grade_column_url(self, course_id):
        """
        Blackboard API url helper method.
        Path: Create course grade column
        """
        return '{base}{path}'.format(
            base=self.enterprise_configuration.blackboard_base_url,
            path=POST_GRADE_COLUMN_PATH.format(course_id=course_id),
        )

    def generate_post_users_grade_url(self, course_id, column_id, user_id):
        """
        Blackboard API url helper method.
        Path: User's grade column entry
        """
        return '{base}{path}'.format(
            base=self.enterprise_configuration.blackboard_base_url,
            path=POST_GRADE_PATH.format(
                course_id=course_id,
                column_id=column_id,
                user_id=user_id,
            ),
        )

    def generate_create_course_content_url(self, course_id):
        """
        Blackboard API url helper method.
        Path: Course's content objects
        """
        return '{base}{path}'.format(
            base=self.enterprise_configuration.blackboard_base_url,
            path=COURSE_CONTENT_PATH.format(course_id=course_id)
        )

    def generate_create_course_content_child_url(self, course_id, content_id):
        """
        Blackboard API url helper method.
        Path: Course content's children objects
        """
        return '{base}{path}'.format(
            base=self.enterprise_configuration.blackboard_base_url,
            path=COURSE_CONTENT_CHILDREN_PATH.format(course_id=course_id, content_id=content_id)
        )

    def generate_course_content_delete_url(self, course_id, content_id):
        """
        Blackboard API url helper method.
        Path: Course content deletion
        """
        return '{base}{path}'.format(
            base=self.enterprise_configuration.blackboard_base_url,
            path=COURSE_CONTENT_DELETE_PATH.format(course_id=course_id, content_id=content_id)
        )

    def _get(self, url, data=None):
        """
        Returns request's get response and raises Client Errors if appropriate.
        """
        get_response = self.session.get(url, params=data)
        if get_response.status_code >= 400:
            raise ClientError(get_response.text, get_response.status_code)
        return get_response

    def _patch(self, url, data):
        """
        Returns request's patch response and raises Client Errors if appropriate.
        """
        patch_response = self.session.patch(url, json=data)
        if patch_response.status_code >= 400:
            raise ClientError(patch_response.text, patch_response.status_code)
        return patch_response

    def _post(self, url, data):
        """
        Returns request's post response and raises Client Errors if appropriate.
        """
        post_response = self.session.post(url, json=data)
        if post_response.status_code >= 400:
            raise ClientError(post_response.text, post_response.status_code)
        return post_response

    def _delete(self, url):
        """
        Returns request's delete response and raises Client Errors if appropriate.
        """
        response = self.session.delete(url)
        if response.status_code >= 400:
            raise ClientError(response.text, response.status_code)
        return response

    def _get_bb_user_id_from_enrollments(self, user_email, course_id):
        """
        Helper method to retrieve a user's Blackboard ID from a list of enrollments in a
        Blackboard class.

        Parameters:
        -----------
            user_email (str): The shared email of the user for both Blackboard and edX
            course_id (str): The Blackboard course ID of which to search enrollments.
        """
        enrollments_response = self._get(self.generate_enrollment_url(course_id)).json()
        for enrollment in enrollments_response.get('results'):
            # No point in checking non-students
            if enrollment.get('courseRoleId') == 'Student':
                contact = enrollment.get('user').get('contact')
                if contact.get('email') == user_email:
                    return enrollment.get('userId')
        raise ClientError(
            'Could not find user={} enrolled in Blackboard course={}'.format(user_email, course_id),
            HTTPStatus.NOT_FOUND.value
        )

    def _get_or_create_integrated_grade_column(self, bb_course_id, grade_column_name, external_id, points_possible=100):
        """
        Helper method to search an edX integrated Blackboard course for the designated edX grade column.
        If the column does not yet exist within the course, create it.

        Parameters:
        -----------
            bb_course_id (str): The Blackboard course ID in which to search for the edX final grade,
            grade column.
        """
        grade_column_response = self._get(self.generate_gradebook_url(bb_course_id))
        parsed_response = grade_column_response.json()
        grade_columns = parsed_response.get('results')

        grade_column_id = None
        for grade_column in grade_columns:
            if grade_column.get('externalId') == external_id:
                grade_column_id = grade_column.get('id')
        if not grade_column_id:
            # Potential customization here per-customer, if the need arises.
            grade_column_data = {
                "externalId": external_id,
                "name": grade_column_name,
                "displayName": grade_column_name,
                "description": "edX learner's grade.",
                "externalGrade": False,
                "score": {
                    "possible": points_possible
                },
                "availability": {
                    "available": "Yes"
                },
                "grading": {
                    "type": "Manual",
                    "scoringModel": "Last",
                    "anonymousGrading": {
                        "type": "None",
                    }
                },
            }

            response = self._post(self.generate_create_grade_column_url(bb_course_id), grade_column_data)
            parsed_response = response.json()
            grade_column_id = parsed_response.get('id')

            # Sanity check that we created the grade column properly
            if not grade_column_id:
                raise ClientError(
                    'Something went wrong while create edX integration grade column for course={}.'.format(
                        bb_course_id
                    ),
                    HTTPStatus.INTERNAL_SERVER_ERROR.value
                )

        return grade_column_id

    def _submit_grade_to_blackboard(self, grade, course_id, grade_column_id, user_id):
        """
        Helper method to post learner data to the integrated blackboard course and then validate the submission of
        grade reporting.
        """
        grade_percent = {'score': grade}
        response = self._patch(
            self.generate_post_users_grade_url(course_id, grade_column_id, user_id),
            grade_percent
        )

        if response.json().get('score') != grade:
            raise ClientError(
                'Failed to post new grade for user={} enrolled in course={}'.format(user_id, course_id),
                HTTPStatus.INTERNAL_SERVER_ERROR.value
            )

        return response

    def _resolve_blackboard_course_id(self, external_id):
        """
        Extract course id from blackboard, given it's externalId
        """
        params = {'externalId': external_id}
        courses_responses = self._get(self.generate_courses_url(), params).json()
        course_response = courses_responses.get('results')

        for course in course_response:
            if course.get('externalId') == external_id:
                return course.get('id')
        return None

    def delete_course_content_from_blackboard(self, bb_course_id, bb_content_id):
        """
        Error handling Helper method that will delete any successful content posts that occurred during
        the error'd transmission.
        """
        delete_course_content_url = urljoin(
            self.enterprise_configuration.blackboard_base_url,
            COURSE_CONTENT_DELETE_PATH.format(course_id=bb_course_id, content_id=bb_content_id),
        )
        resp = self._delete(delete_course_content_url)
        return resp

    def delete_course_from_blackboard(self, bb_course_id, bb_content_id=None):
        """
        Error handling Helper method that will delete any already made, successful post requests that occurred during
        the content creation flow.
        """
        # Remove the content if it exists
        if bb_content_id:
            self.delete_course_content_from_blackboard(bb_course_id, bb_content_id)

        # Remove the course
        delete_course_path = urljoin(
            self.enterprise_configuration.blackboard_base_url,
            COURSE_V3_PATH.format(course_id=bb_course_id),
        )
        resp = self._delete(delete_course_path)
        return resp

    def update_integration_content_for_course(self, bb_course_id, channel_metadata_item):
        """
        Helper method to update the blackboard course content page with the integration custom information.
        Differs from course customization creation in that we don't delete the course if things fail.
        """
        content_url = self.generate_create_course_content_url(bb_course_id)
        error_message = ''
        try:
            content_resp = self._post(content_url, channel_metadata_item.get('course_content_metadata'))
            bb_content_id = content_resp.json().get('id')
        except ClientError as error:
            bb_content_id = None
            error_message = ' and received error response={}'.format(error.message)

        if not bb_content_id:
            error_message = '' if not error_message else error_message
            raise ClientError(
                'Something went wrong while creating course content object on Blackboard. Could not retrieve content '
                'ID{}.'.format(error_message),
                HTTPStatus.NOT_FOUND.value
            )

        try:
            content_child_url = self.generate_create_course_content_child_url(bb_course_id, bb_content_id)
            course_fully_created_response = self._post(
                content_child_url, channel_metadata_item.get('course_child_content_metadata')
            )
            content_child_id = course_fully_created_response.json().get('id')
        except ClientError as error:
            content_child_id = None
            error_message = ' and received error response={}'.format(error.message)

        if not content_child_id:
            error_message = '' if not error_message else error_message
            error_handling_response = self.delete_course_content_from_blackboard(bb_course_id, bb_content_id)

            raise ClientError(
                'Something went wrong while creating course content child object on Blackboard. Could not retrieve a '
                'content child ID and got error response={}. Deleted associated course content shell with response: '
                '(status_code={}, body={})'.format(
                    error_message,
                    error_handling_response.status_code,
                    error_handling_response.text
                ),
                HTTPStatus.NOT_FOUND.value
            )

        return course_fully_created_response

    def create_integration_content_for_course(self, bb_course_id, channel_metadata_item):
        """
        Helper method to generate the default blackboard course content page with the integration custom information.
        """
        content_url = self.generate_create_course_content_url(bb_course_id)
        error_message = ''
        try:
            content_resp = self._post(content_url, channel_metadata_item.get('course_content_metadata'))
            bb_content_id = content_resp.json().get('id')
        except ClientError as error:
            bb_content_id = None
            error_message = ' and received error response={}'.format(error.message)

        if not bb_content_id:
            error_handling_response = self.delete_course_from_blackboard(bb_course_id)
            error_message = '' if not error_message else error_message
            raise ClientError(
                'Something went wrong while creating course content object on Blackboard. Could not retrieve content '
                'ID{}. Deleted course with response (status_code={}, body={})'.format(
                    error_message,
                    error_handling_response.status_code,
                    error_handling_response.text
                ),
                HTTPStatus.NOT_FOUND.value
            )

        try:
            content_child_url = self.generate_create_course_content_child_url(bb_course_id, bb_content_id)
            course_fully_created_response = self._post(
                content_child_url, channel_metadata_item.get('course_child_content_metadata')
            )
            content_child_id = course_fully_created_response.json().get('id')
        except ClientError as error:
            content_child_id = None
            error_message = ' and received error response={}'.format(error.message)

        if not content_child_id:
            error_message = '' if not error_message else error_message
            error_handling_response = self.delete_course_from_blackboard(bb_course_id, bb_content_id)
            raise ClientError(
                'Something went wrong while creating course content child object on Blackboard. Could not retrieve a '
                'content child ID and got error response={}. Deleted associated course and content with response: '
                '(status_code={}, body={})'.format(
                    error_message,
                    error_handling_response.status_code,
                    error_handling_response.text
                ),
                HTTPStatus.NOT_FOUND.value
            )

        return course_fully_created_response

    def cleanup_duplicate_assignment_records(self, courses):
        """
        Not implemented yet.
        """
        LOGGER.error("Blackboard integrated channel does not yet support assignment deduplication.")

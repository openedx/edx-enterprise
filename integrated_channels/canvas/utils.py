'''Collection of static util methods for various Canvas operations'''
import logging
from http import HTTPStatus

from requests.utils import quote

from integrated_channels.exceptions import ClientError
from integrated_channels.utils import generate_formatted_log

LOGGER = logging.getLogger(__name__)


class CanvasUtil:
    """
    A util to make various util functions related to Canvas easier and co-located.

    Every method in this class is static and stateless. They all need at least
        - enterprise_configuration
        - session
    plus additional relevant arguments.

    Usage example:
        canvas_api_client._create_session() # if needed
        CanvasUtil.find_course_in_account(
            canvas_api_client.enterprise_configuration,
            canvas_api_client.session,
            course_id,
            account_id,
        )
    """

    @staticmethod
    def find_root_canvas_account(enterprise_configuration, session):
        """
        Attempts to find root account id from Canvas.

        Arguments:
          - enterprise_configuration (EnterpriseCustomerPluginConfiguration)
          - session (requests.Session)

        If root account cannot be found, returns None
        """
        url = "{}/api/v1/accounts".format(enterprise_configuration.canvas_base_url)
        resp = session.get(url)
        all_accounts = resp.json()
        root_account = None
        for account in all_accounts:
            if account['parent_account_id'] is None:
                root_account = account
                break
        return root_account

    @staticmethod
    def find_course_in_account(enterprise_configuration, session, canvas_account_id, edx_course_id):
        """
        Search course by edx_course_id (used as integration_id in canvas) under provided account.
        It will even return courses that are in the 'deleted' state in Canvas, so we can correctly
        skip these courses in logic as needed.

        Note: we do not need to follow pagination here since it would be extremely unlikely
        that searching by a specific edx_course_id results in many records, we generally only
        expect 1 record to come back anyway.

        Arguments:
          - enterprise_configuration (EnterpriseCustomerPluginConfiguration)
          - session (requests.Session)
          - canvas_account_id (Number) : account to search courses in
          - edx_course_id (str) : edX course key

        Ref: https://canvas.instructure.com/doc/api/accounts.html#method.accounts.courses_api

        The `&state[]=all` is added so we can also fetch priorly 'delete'd courses as well
        """
        url = "{}/api/v1/accounts/{}/courses/?search_term={}&state[]=all".format(
            enterprise_configuration.canvas_base_url,
            canvas_account_id,
            quote(edx_course_id),
        )
        resp = session.get(url)
        all_courses_response = resp.json()

        if resp.status_code >= 400:
            message = 'Failed to find a course under Canvas account: {account_id}'.format(
                account_id=canvas_account_id
            )
            if 'reason' in all_courses_response:
                message = '{} : Reason = {}'.format(message, all_courses_response['reason'])
            elif 'errors' in all_courses_response:
                message = '{} : Errors = {}'.format(message, str(all_courses_response['errors']))
            raise ClientError(
                message,
                resp.status_code
            )

        course_found = None
        for course in all_courses_response:
            if course['integration_id'] == edx_course_id:
                course_found = course
                break
        return course_found

    @staticmethod
    def get_course_id_from_edx_course_id(enterprise_configuration, session, edx_course_id):
        """
        Uses the Canvas search api to find a course by edx_course_id

        Arguments:
          - enterprise_configuration (EnterpriseCustomerPluginConfiguration)
          - session (requests.Session)
          - edx_course_id (str) : edX course key

        Returns:
            canvas_course_id (string): id from Canvas
        """
        course = CanvasUtil.find_course_by_course_id(
            enterprise_configuration,
            session,
            edx_course_id,
        )

        if not course:
            raise ClientError(
                "No Canvas courses found with associated edx course ID: {}.".format(
                    edx_course_id
                ),
                HTTPStatus.NOT_FOUND.value
            )
        return course['id']

    @staticmethod
    def find_course_by_course_id(
        enterprise_configuration,
        session,
        edx_course_id,
    ):
        """
        First attempts to find courase under current account id
        As fallback, to account for cases where course was priorly transmitted to a different
        account, it also searches under the root account for the course.

        Arguments:
          - enterprise_configuration (EnterpriseCustomerPluginConfiguration)
          - session (requests.Session)
          - edx_course_id (str) : edX course key

        Returns:
        - Course dict if the course found in Canvas,
        - None otherwise
        """
        course = CanvasUtil.find_course_in_account(
            enterprise_configuration,
            session,
            enterprise_configuration.canvas_account_id,
            edx_course_id,
        )
        if not course:
            # now let's try the root account instead (searches under all subaccounts)
            root_canvas_account = CanvasUtil.find_root_canvas_account(enterprise_configuration, session)
            course = CanvasUtil.find_course_in_account(
                enterprise_configuration,
                session,
                root_canvas_account['id'],
                edx_course_id,
            )
            if course:
                LOGGER.info(generate_formatted_log(
                    'canvas',
                    enterprise_configuration.enterprise_customer.uuid,
                    None,
                    edx_course_id,
                    'Found course under root Canvas account'
                ))
        return course

# -*- coding: utf-8 -*-
"""
Custom Django Admin views used in enterprise app.
"""
from __future__ import absolute_import, unicode_literals

import datetime
import json
import logging

from edx_rest_api_client.exceptions import HttpClientError

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth import get_permission_codename
from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils.http import urlquote
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from django.views.generic import View

from enterprise.admin.forms import ManageLearnersForm, TransmitEnterpriseCoursesForm
from enterprise.admin.utils import (
    ValidationMessages,
    email_or_username__to__email,
    get_course_runs_from_program,
    get_earliest_start_date_from_program,
    parse_csv,
    split_usernames_and_emails,
    validate_email_to_link,
)
from enterprise.api_client.lms import EnrollmentApiClient
from enterprise.models import (
    EnrollmentNotificationEmailTemplate,
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerUser,
    PendingEnterpriseCustomerUser,
)
from enterprise.utils import get_configuration_value_for_site, send_email_notification_message, track_enrollment


class TemplatePreviewView(View):
    """
    Renders a given NotificationTemplate object to HTML for online viewing.
    """
    view_type_contexts = {
        "course": {
            "enrolled_in": {
                "name": "OpenEdX Demo Course",
                "url": "http://example.com/courses/edx-demo-course",
                "type": "course",
                "start": datetime.datetime.strptime('2016-01-01', '%Y-%m-%d')
            },
            "organization_name": "OpenEdX",
        },
        "program": {
            "enrolled_in": {
                "name": "OpenEdX Demo Program",
                "url": "http://example.com/programs/edx-demo-program",
                "type": "program",
                "branding": "MicroMasters",
                "start": datetime.datetime.strptime('2016-01-01', '%Y-%m-%d')
            },
            "organization_name": "OpenEdX",
        },
    }

    def get(self, request, template_id, view_type):
        """
        Render the given template with the stock data.
        """
        template = get_object_or_404(EnrollmentNotificationEmailTemplate, pk=template_id)
        if view_type not in self.view_type_contexts:
            return HttpResponse(status=404)
        base_context = self.view_type_contexts[view_type].copy()
        base_context.update({'user_name': self.get_user_name(request)})
        return HttpResponse(template.render_html_template(base_context), content_type='text/html')

    @staticmethod
    def get_user_name(request):
        """
        Get a human-readable name for the user.
        """
        return request.user.first_name or request.user.username


class EnterpriseCustomerTransmitCoursesView(View):
    """
    Transmit courses view.

    Allows transmitting of courses metadata for provided enterprise.
    """
    template = 'enterprise/admin/transmit_courses_metadata.html'

    class ContextParameters(object):
        """
        Namespace-style class for custom context parameters.
        """
        ENTERPRISE_CUSTOMER = 'enterprise_customer'
        TRANSMIT_COURSES_METADATA_FORM = 'transmit_courses_metadata_form'

    @staticmethod
    def _build_admin_context(request, customer):
        """
        Build common admin context.
        """
        opts = customer._meta
        codename = get_permission_codename('change', opts)
        has_change_permission = request.user.has_perm('%s.%s' % (opts.app_label, codename))
        return {
            'has_change_permission': has_change_permission,
            'opts': opts
        }

    def _build_context(self, request, enterprise_customer_uuid):
        """
        Build common context parts used by different handlers in this view.
        """
        enterprise_customer = EnterpriseCustomer.objects.get(uuid=enterprise_customer_uuid)  # pylint: disable=no-member

        context = {
            self.ContextParameters.ENTERPRISE_CUSTOMER: enterprise_customer,
        }
        context.update(admin.site.each_context(request))
        context.update(self._build_admin_context(request, enterprise_customer))
        return context

    def get(self, request, enterprise_customer_uuid):
        """
        Handle GET request - render "Transmit courses metadata" form.

        Arguments:
            request (django.http.request.HttpRequest): Request instance
            enterprise_customer_uuid (str): Enterprise Customer UUID

        Returns:
            django.http.response.HttpResponse: HttpResponse
        """
        context = self._build_context(request, enterprise_customer_uuid)
        transmit_courses_metadata_form = TransmitEnterpriseCoursesForm()
        context.update({self.ContextParameters.TRANSMIT_COURSES_METADATA_FORM: transmit_courses_metadata_form})

        return render(request, self.template, context)

    def post(self, request, enterprise_customer_uuid):
        """
        Handle POST request - handle form submissions.

        Arguments:
            request (django.http.request.HttpRequest): Request instance
            enterprise_customer_uuid (str): Enterprise Customer UUID
        """
        transmit_courses_metadata_form = TransmitEnterpriseCoursesForm(request.POST)

        # check that form data is well-formed
        if transmit_courses_metadata_form.is_valid():
            channel_worker_username = transmit_courses_metadata_form.cleaned_data['channel_worker_username']

            # call `transmit_course_metadata` management command to trigger
            # transmission of enterprise courses metadata
            call_command(
                'transmit_course_metadata',
                '--catalog_user', channel_worker_username,
                enterprise_customer=enterprise_customer_uuid
            )

            # Redirect to GET
            return HttpResponseRedirect('')

        context = self._build_context(request, enterprise_customer_uuid)
        context.update({self.ContextParameters.TRANSMIT_COURSES_METADATA_FORM: transmit_courses_metadata_form})
        return render(request, self.template, context)


class EnterpriseCustomerManageLearnersView(View):
    """
    Manage Learners view.

    Lists learners linked to chosen Enterprise Customer and allows adding and deleting them.
    """
    template = "enterprise/admin/manage_learners.html"

    class ContextParameters(object):
        """
        Namespace-style class for custom context parameters.
        """
        ENTERPRISE_CUSTOMER = "enterprise_customer"
        LEARNERS = "learners"
        PENDING_LEARNERS = "pending_learners"
        MANAGE_LEARNERS_FORM = "manage_learners_form"
        SEARCH_KEYWORD = "search_keyword"
        ENROLLMENT_URL = 'ENROLLMENT_API_ROOT_URL'

    @staticmethod
    def _build_admin_context(request, customer):
        """
        Build common admin context.
        """
        opts = customer._meta
        codename = get_permission_codename("change", opts)
        has_change_permission = request.user.has_perm("%s.%s" % (opts.app_label, codename))
        return {
            "has_change_permission": has_change_permission,
            "opts": opts
        }

    def _build_context(self, request, customer_uuid):
        """
        Build common context parts used by different handlers in this view.
        """
        # TODO: pylint acts stupid - find a way around it without suppressing
        enterprise_customer = EnterpriseCustomer.objects.get(uuid=customer_uuid)  # pylint: disable=no-member

        search_keyword = self.get_search_keyword(request)
        linked_learners = self.get_enterprise_customer_user_queryset(search_keyword, customer_uuid)
        pending_linked_learners = self.get_pending_users_queryset(search_keyword, customer_uuid)

        context = {
            self.ContextParameters.ENTERPRISE_CUSTOMER: enterprise_customer,
            self.ContextParameters.PENDING_LEARNERS: pending_linked_learners,
            self.ContextParameters.LEARNERS: linked_learners,
            self.ContextParameters.SEARCH_KEYWORD: search_keyword or '',
            self.ContextParameters.ENROLLMENT_URL: settings.LMS_ENROLLMENT_API_PATH,
        }
        context.update(admin.site.each_context(request))
        context.update(self._build_admin_context(request, enterprise_customer))
        return context

    def get_search_keyword(self, request):
        """
        Retrieve the search querystring from the GET parameters.
        """
        return request.GET.get('q', None)

    def get_enterprise_customer_user_queryset(self, search_keyword, customer_uuid):
        """
        Get the list of EnterpriseCustomerUsers we want to render.

        Args:
            search_keyword (str): The keyword to search for in users' email addresses and usernames.
            customer_uuid (str): A unique identifier to filter down to only users linked to a
            particular EnterpriseCustomer.
        """
        learners = EnterpriseCustomerUser.objects.filter(enterprise_customer__uuid=customer_uuid)

        if search_keyword is not None:
            user_ids = learners.values_list('user_id', flat=True)
            matching_users = User.objects.filter(
                Q(pk__in=user_ids),
                Q(email__icontains=search_keyword) | Q(username__icontains=search_keyword)
            )
            matching_user_ids = matching_users.values_list('pk', flat=True)
            learners = learners.filter(user_id__in=matching_user_ids)

        return learners

    def get_pending_users_queryset(self, search_keyword, customer_uuid):
        """
        Get the list of PendingEnterpriseCustomerUsers we want to render.

        Args:
            search_keyword (str): The keyword to search for in pending users' email addresses.
            customer_uuid (str): A unique identifier to filter down to only pending users
            linked to a particular EnterpriseCustomer.
        """
        queryset = PendingEnterpriseCustomerUser.objects.filter(
            enterprise_customer__uuid=customer_uuid
        )

        if search_keyword is not None:
            queryset = queryset.filter(user_email__icontains=search_keyword)

        return queryset

    @classmethod
    def _handle_singular(cls, enterprise_customer, manage_learners_form):
        """
        Link single user by email or username.

        Arguments:
            enterprise_customer (EnterpriseCustomer): learners will be linked to this Enterprise Customer instance
            manage_learners_form (ManageLearnersForm): bound ManageLearners form instance
        """
        form_field_value = manage_learners_form.cleaned_data[ManageLearnersForm.Fields.EMAIL_OR_USERNAME]
        email = email_or_username__to__email(form_field_value)
        try:
            validate_email_to_link(email, form_field_value, ValidationMessages.INVALID_EMAIL_OR_USERNAME, True)
        except ValidationError as exc:
            manage_learners_form.add_error(ManageLearnersForm.Fields.EMAIL_OR_USERNAME, exc)
        else:
            EnterpriseCustomerUser.objects.link_user(enterprise_customer, email)
            return [email]

    @classmethod
    def _handle_bulk_upload(cls, enterprise_customer, manage_learners_form, request, email_list=None):
        """
        Bulk link users by email.

        Arguments:
            enterprise_customer (EnterpriseCustomer): learners will be linked to this Enterprise Customer instance
            manage_learners_form (ManageLearnersForm): bound ManageLearners form instance
            request (django.http.request.HttpRequest): HTTP Request instance
            email_list (iterable): A list of pre-processed email addresses to handle using the form
        """
        errors = []
        emails = set()
        already_linked_emails = []
        duplicate_emails = []
        csv_file = manage_learners_form.cleaned_data[ManageLearnersForm.Fields.BULK_UPLOAD]
        if email_list:
            parsed_csv = [{ManageLearnersForm.CsvColumns.EMAIL: email} for email in email_list]
        else:
            parsed_csv = parse_csv(csv_file, expected_columns={ManageLearnersForm.CsvColumns.EMAIL})

        try:
            for index, row in enumerate(parsed_csv):
                email = row[ManageLearnersForm.CsvColumns.EMAIL]
                try:
                    already_linked = validate_email_to_link(email, ignore_existing=True)
                except ValidationError as exc:
                    message = _("Error at line {line}: {message}\n").format(line=index + 1, message=exc)
                    errors.append(message)
                else:
                    if already_linked:
                        already_linked_emails.append((email, already_linked.enterprise_customer))
                    elif email in emails:
                        duplicate_emails.append(email)
                    else:
                        emails.add(email)
        except ValidationError as exc:
            errors.append(exc)

        if errors:
            manage_learners_form.add_error(
                ManageLearnersForm.Fields.GENERAL_ERRORS, ValidationMessages.BULK_LINK_FAILED
            )
            for error in errors:
                manage_learners_form.add_error(ManageLearnersForm.Fields.BULK_UPLOAD, error)
            return

        # There were no errors. Now do the actual linking:
        for email in emails:
            EnterpriseCustomerUser.objects.link_user(enterprise_customer, email)

        # Report what happened:
        count = len(emails)
        messages.success(request, ungettext(
            "{count} new learner was added to {enterprise_customer_name}.",
            "{count} new learners were added to {enterprise_customer_name}.",
            count
        ).format(count=count, enterprise_customer_name=enterprise_customer.name))
        this_customer_linked_emails = [
            email for email, customer in already_linked_emails if customer == enterprise_customer
        ]
        other_customer_linked_emails = [
            email for email, __ in already_linked_emails if email not in this_customer_linked_emails
        ]
        if this_customer_linked_emails:
            messages.warning(
                request,
                _(
                    "The following learners were already associated with this Enterprise "
                    "Customer: {list_of_emails}"
                ).format(
                    list_of_emails=", ".join(this_customer_linked_emails)
                )
            )
        if other_customer_linked_emails:
            messages.warning(
                request,
                _(
                    "The following learners are already associated with "
                    "another Enterprise Customer. These learners were not "
                    "added to {enterprise_customer_name}: {list_of_emails}"
                ).format(
                    enterprise_customer_name=enterprise_customer.name,
                    list_of_emails=", ".join(other_customer_linked_emails),
                )
            )
        if duplicate_emails:
            messages.warning(
                request,
                _(
                    "The following duplicate email addresses were not added: "
                    "{list_of_emails}"
                ).format(
                    list_of_emails=", ".join(duplicate_emails)
                )
            )
        # Build a list of all the emails that we can act on further; that is,
        # emails that we either linked to this customer, or that were linked already.
        all_processable_emails = list(emails) + this_customer_linked_emails

        return all_processable_emails

    @classmethod
    def enroll_user(cls, enterprise_customer, user, course_mode, *course_ids):
        """
        Enroll a single user in any number of courses using a particular course mode.

        Args:
            enterprise_customer: The EnterpriseCustomer which is sponsoring the enrollment
            user: The user who needs to be enrolled in the course
            course_mode: The mode with which the enrollment should be created
            *course_ids: An iterable containing any number of course IDs to eventually enroll the user in.

        Returns:
            Boolean: Whether or not enrollment succeeded for all courses specified
        """
        enterprise_customer_user, __ = EnterpriseCustomerUser.objects.get_or_create(
            enterprise_customer=enterprise_customer,
            user_id=user.id
        )
        enrollment_client = EnrollmentApiClient()
        succeeded = True
        for course_id in course_ids:
            try:
                enrollment_client.enroll_user_in_course(user.username, course_id, course_mode)
            except HttpClientError as exc:
                succeeded = False
                default_message = 'No error message provided'
                try:
                    error_message = json.loads(exc.content.decode()).get('message', default_message)
                except ValueError:
                    error_message = default_message
                logging.error(
                    'Error while enrolling user %(user)s: %(message)s',
                    dict(user=user.username, message=error_message)
                )
            else:
                __, created = EnterpriseCourseEnrollment.objects.get_or_create(
                    enterprise_customer_user=enterprise_customer_user,
                    course_id=course_id
                )
                if created:
                    track_enrollment('admin-enrollment', user.id, course_id)
        return succeeded

    @classmethod
    def get_users_by_email(cls, emails):
        """
        Accept a list of emails, and separate them into users that exist on OpenEdX and users who don't.

        Args:
            emails: An iterable of email addresses to split between existing and nonexisting

        Returns:
            users: Queryset of users who exist in the OpenEdX platform and who were in the list of email addresses
            missing_emails: List of unique emails which were in the original list, but do not yet exist as users
        """
        users = User.objects.filter(email__in=emails)
        present_emails = users.values_list('email', flat=True)
        missing_emails = list(set(emails) - set(present_emails))
        return users, missing_emails

    @classmethod
    def enroll_users_in_program(cls, enterprise_customer, program_details, course_mode, emails):
        """
        Enroll existing users in all courses in a program, and create pending enrollments for nonexisting users.

        Args:
            enterprise_customer: The EnterpriseCustomer which is sponsoring the enrollment
            program_details: The details of the program in which we're enrolling
            course_mode (str): The mode with which we're enrolling in the program
            emails: An iterable of email addresses which need to be enrolled

        Returns:
            successes: A list of users who were successfully enrolled in all courses of the program
            pending: A list of PendingEnterpriseCustomerUsers who were successfully linked and had
                pending enrollments created for them in the database
            failures: A list of users who could not be enrolled in the program
        """
        existing_users, unregistered_emails = cls.get_users_by_email(emails)
        course_ids = get_course_runs_from_program(program_details)

        successes = []
        pending = []
        failures = []

        for user in existing_users:
            succeeded = cls.enroll_user(enterprise_customer, user, course_mode, *course_ids)
            if succeeded:
                successes.append(user)
            else:
                failures.append(user)

        for email in unregistered_emails:
            pending_user = enterprise_customer.enroll_user_pending_registration(
                email,
                course_mode,
                *course_ids
            )
            pending.append(pending_user)

        return successes, pending, failures

    @classmethod
    def enroll_users_in_course(cls, enterprise_customer, course_id, course_mode, emails):
        """
        Enroll existing users in a course, and create a pending enrollment for nonexisting users.

        Args:
            enterprise_customer: The EnterpriseCustomer which is sponsoring the enrollment
            course_id (str): The unique identifier of the course in which we're enrolling
            course_mode (str): The mode with which we're enrolling in the course
            emails: An iterable of email addresses which need to be enrolled

        Returns:
            successes: A list of users who were successfully enrolled in the course
            pending: A list of PendingEnterpriseCustomerUsers who were successfully linked and had
                pending enrollments created for them in the database
            failures: A list of users who could not be enrolled in the course
        """
        existing_users, unregistered_emails = cls.get_users_by_email(emails)

        successes = []
        pending = []
        failures = []

        for user in existing_users:
            succeeded = cls.enroll_user(enterprise_customer, user, course_mode, course_id)
            if succeeded:
                successes.append(user)
            else:
                failures.append(user)

        for email in unregistered_emails:
            pending_user = enterprise_customer.enroll_user_pending_registration(
                email,
                course_mode,
                course_id
            )
            pending.append(pending_user)

        return successes, pending, failures

    @classmethod
    def send_messages(cls, http_request, message_requests):
        """
        Deduplicate any outgoing message requests, and send the remainder.

        Args:
            http_request: The HTTP request in whose response we want to embed the messages
            message_requests: A list of undeduplicated messages in the form of tuples of message type
                and text- for example, ('error', 'Something went wrong')
        """
        deduplicated_messages = set(message_requests)
        for msg_type, text in deduplicated_messages:
            message_function = getattr(messages, msg_type)
            message_function(http_request, text)

    @classmethod
    def notify_program_learners(cls, enterprise_customer, program_details, users):
        """
        Notify learners about a program in which they've been enrolled.

        Args:
            enterprise_customer: The EnterpriseCustomer being linked to
            program_details: Details about the specific program the learners were enrolled in
            users: An iterable of the users or pending users who were enrolled
        """
        program_name = program_details.get('title')
        program_branding = program_details.get('type')
        program_uuid = program_details.get('uuid')

        lms_root_url = get_configuration_value_for_site(
            enterprise_customer.site,
            'LMS_ROOT_URL',
            settings.LMS_ROOT_URL
        )
        program_path = urlquote(
            '/dashboard/programs/{program_uuid}/?tpa_hint={tpa_hint}'.format(
                program_uuid=program_uuid,
                tpa_hint=enterprise_customer.identity_provider,
            )
        )
        destination_url = '{site}/{login_or_register}?next={program_path}'.format(
            site=lms_root_url,
            login_or_register='{login_or_register}',
            program_path=program_path
        )
        program_type = 'program'
        program_start = get_earliest_start_date_from_program(program_details)

        with mail.get_connection() as email_conn:
            for user in users:
                login_or_register = 'register' if isinstance(user, PendingEnterpriseCustomerUser) else 'login'
                destination_url = destination_url.format(login_or_register=login_or_register)
                send_email_notification_message(
                    user=user,
                    enrolled_in={
                        'name': program_name,
                        'url': destination_url,
                        'type': program_type,
                        'start': program_start,
                        'branding': program_branding,
                    },
                    enterprise_customer=enterprise_customer,
                    email_connection=email_conn
                )

    @classmethod
    def get_success_enrollment_message(cls, users, enrolled_in):
        """
        Create message for the users who were enrolled in a course or program.

        Args:
            users: An iterable of users who were successfully enrolled
            enrolled_in (str): A string identifier for the course or program the users were enrolled in

        Returns:
            tuple: A 2-tuple containing a message type and message text
        """
        enrolled_count = len(users)
        return (
            'success',
            ungettext(
                '{enrolled_count} learner was enrolled in {enrolled_in}.',
                '{enrolled_count} learners were enrolled in {enrolled_in}.',
                enrolled_count,
            ).format(
                enrolled_count=enrolled_count,
                enrolled_in=enrolled_in,
            )
        )

    @classmethod
    def get_failed_enrollment_message(cls, users, enrolled_in):
        """
        Create message for the users who were not able to be enrolled in a course or program.

        Args:
            users: An iterable of users who were not successfully enrolled
            enrolled_in (str): A string identifier for the course or program with which enrollment was attempted

        Returns:
        tuple: A 2-tuple containing a message type and message text
        """
        failed_emails = [user.email for user in users]
        return (
            'error',
            _(
                'The following learners could not be enrolled in {enrolled_in}: {user_list}'
            ).format(
                enrolled_in=enrolled_in,
                user_list=', '.join(failed_emails),
            )
        )

    @classmethod
    def get_pending_enrollment_message(cls, pending_users, enrolled_in):
        """
        Create message for the users who were enrolled in a course or program.

        Args:
            users: An iterable of PendingEnterpriseCustomerUsers who were successfully linked with a pending enrollment
            enrolled_in (str): A string identifier for the course or program the pending users were linked to

        Returns:
            tuple: A 2-tuple containing a message type and message text
        """
        pending_emails = [pending_user.user_email for pending_user in pending_users]
        return (
            'warning',
            _(
                "The following learners do not have an account on "
                "{platform_name}. They have not been enrolled in "
                "{enrolled_in}. When these learners create an account, they will "
                "be enrolled automatically: {pending_email_list}"
            ).format(
                platform_name=settings.PLATFORM_NAME,
                enrolled_in=enrolled_in,
                pending_email_list=', '.join(pending_emails),
            )
        )

    @classmethod
    def _enroll_users(
            cls,
            request,
            enterprise_customer,
            emails,
            mode,
            course_id=None,
            program_details=None,
            notify=True
    ):
        """
        Enroll the users with the given email addresses to the courses specified, either specifically or by program.

        Args:
            cls (type): The EnterpriseCustomerManageLearnersView class itself
            request: The HTTP request the enrollment is being created by
            enterprise_customer: The instance of EnterpriseCustomer whose attached users we're enrolling
            emails: An iterable of strings containing email addresses to enroll in a course
            mode: The enrollment mode the users will be enrolled in the course with
            course_id: The ID of the course in which we want to enroll
            program_details: Details about a program in which we want to enroll
            notify: Whether to notify (by email) the users that have been enrolled
        """
        pending_messages = []

        if course_id:
            succeeded, pending, failed = cls.enroll_users_in_course(
                enterprise_customer=enterprise_customer,
                course_id=course_id,
                course_mode=mode,
                emails=emails,
            )
            all_successes = succeeded + pending
            if notify:
                enterprise_customer.notify_enrolled_learners(
                    catalog_api_user=request.user,
                    course_id=course_id,
                    users=all_successes,
                )
            if succeeded:
                pending_messages.append(cls.get_success_enrollment_message(succeeded, course_id))
            if failed:
                pending_messages.append(cls.get_failed_enrollment_message(failed, course_id))
            if pending:
                pending_messages.append(cls.get_pending_enrollment_message(pending, course_id))

        if program_details:
            succeeded, pending, failed = cls.enroll_users_in_program(
                enterprise_customer=enterprise_customer,
                program_details=program_details,
                course_mode=mode,
                emails=emails,
            )
            all_successes = succeeded + pending
            if notify:
                cls.notify_program_learners(
                    enterprise_customer=enterprise_customer,
                    program_details=program_details,
                    users=all_successes
                )
            program_identifier = program_details.get('title', program_details.get('uuid', _('the program')))
            if succeeded:
                pending_messages.append(cls.get_success_enrollment_message(succeeded, program_identifier))
            if failed:
                pending_messages.append(cls.get_failed_enrollment_message(failed, program_identifier))
            if pending:
                pending_messages.append(cls.get_pending_enrollment_message(pending, program_identifier))

        cls.send_messages(request, pending_messages)

    def get(self, request, customer_uuid):
        """
        Handle GET request - render linked learners list and "Link learner" form.

        Arguments:
            request (django.http.request.HttpRequest): Request instance
            customer_uuid (str): Enterprise Customer UUID

        Returns:
            django.http.response.HttpResponse: HttpResponse
        """
        context = self._build_context(request, customer_uuid)
        manage_learners_form = ManageLearnersForm(
            user=request.user,
            enterprise_customer=context[self.ContextParameters.ENTERPRISE_CUSTOMER]
        )
        context.update({self.ContextParameters.MANAGE_LEARNERS_FORM: manage_learners_form})

        return render(request, self.template, context)

    def post(self, request, customer_uuid):
        """
        Handle POST request - handle form submissions.

        Arguments:
            request (django.http.request.HttpRequest): Request instance
            customer_uuid (str): Enterprise Customer UUID

        Returns:
            django.http.response.HttpResponse: HttpResponse
        """
        enterprise_customer = EnterpriseCustomer.objects.get(uuid=customer_uuid)  # pylint: disable=no-member
        manage_learners_form = ManageLearnersForm(
            request.POST,
            request.FILES,
            user=request.user,
            enterprise_customer=enterprise_customer
        )

        # initial form validation - check that form data is well-formed
        if manage_learners_form.is_valid():
            email_field_as_bulk_input = split_usernames_and_emails(
                manage_learners_form.cleaned_data[ManageLearnersForm.Fields.EMAIL_OR_USERNAME]
            )
            is_bulk_entry = len(email_field_as_bulk_input) > 1
            # The form is valid. Call the appropriate helper depending on the mode:
            mode = manage_learners_form.cleaned_data[ManageLearnersForm.Fields.MODE]
            if mode == ManageLearnersForm.Modes.MODE_SINGULAR and not is_bulk_entry:
                linked_learners = self._handle_singular(enterprise_customer, manage_learners_form)
            elif mode == ManageLearnersForm.Modes.MODE_SINGULAR:
                linked_learners = self._handle_bulk_upload(
                    enterprise_customer,
                    manage_learners_form,
                    request,
                    email_list=email_field_as_bulk_input
                )
            else:
                linked_learners = self._handle_bulk_upload(enterprise_customer, manage_learners_form, request)

        # _handle_form might add form errors, so we check if it is still valid
        if manage_learners_form.is_valid():
            course_details = manage_learners_form.cleaned_data.get(ManageLearnersForm.Fields.COURSE)
            program_details = manage_learners_form.cleaned_data.get(ManageLearnersForm.Fields.PROGRAM)

            notification_type = manage_learners_form.cleaned_data.get(ManageLearnersForm.Fields.NOTIFY)
            notify = notification_type == ManageLearnersForm.NotificationTypes.BY_EMAIL

            course_id = None
            if course_details:
                course_id = course_details['course_id']

            if course_id or program_details:
                course_mode = manage_learners_form.cleaned_data[ManageLearnersForm.Fields.COURSE_MODE]
                self._enroll_users(
                    request=request,
                    enterprise_customer=enterprise_customer,
                    emails=linked_learners,
                    mode=course_mode,
                    course_id=course_id,
                    program_details=program_details,
                    notify=notify,
                )

            # Redirect to GET if everything went smooth.
            return HttpResponseRedirect("")

        # if something went wrong - display bound form on the page
        context = self._build_context(request, customer_uuid)
        context.update({self.ContextParameters.MANAGE_LEARNERS_FORM: manage_learners_form})
        return render(request, self.template, context)

    def delete(self, request, customer_uuid):
        """
        Handle DELETE request - handle unlinking learner.

        Arguments:
            request (django.http.request.HttpRequest): Request instance
            customer_uuid (str): Enterprise Customer UUID

        Returns:
            django.http.response.HttpResponse: HttpResponse
        """
        # TODO: pylint acts stupid - find a way around it without suppressing
        enterprise_customer = EnterpriseCustomer.objects.get(uuid=customer_uuid)  # pylint: disable=no-member
        email_to_unlink = request.GET["unlink_email"]
        try:
            EnterpriseCustomerUser.objects.unlink_user(
                enterprise_customer=enterprise_customer, user_email=email_to_unlink
            )
        except (EnterpriseCustomerUser.DoesNotExist, PendingEnterpriseCustomerUser.DoesNotExist):
            message = _("Email {email} is not associated with Enterprise "
                        "Customer {ec_name}").format(
                            email=email_to_unlink, ec_name=enterprise_customer.name)
            return HttpResponse(message, content_type="application/json", status=404)

        return HttpResponse(
            json.dumps({}),
            content_type="application/json"
        )

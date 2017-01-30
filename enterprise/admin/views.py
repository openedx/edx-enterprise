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
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from django.views.generic import View

from enterprise.admin.forms import ManageLearnersForm
from enterprise.admin.utils import (ValidationMessages, email_or_username__to__email, get_course_runs_from_program,
                                    get_earliest_start_date_from_program, parse_csv, split_usernames_and_emails,
                                    validate_email_to_link)
from enterprise.course_catalog_api import CourseCatalogApiClient
from enterprise.lms_api import EnrollmentApiClient, parse_lms_api_datetime
from enterprise.models import (EnrollmentNotificationEmailTemplate, EnterpriseCourseEnrollment, EnterpriseCustomer,
                               EnterpriseCustomerUser, PendingEnrollment, PendingEnterpriseCustomerUser)
from enterprise.utils import ConditionalEmailConnection, get_reversed_url_by_site, send_email_notification_message


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
            self.ContextParameters.ENROLLMENT_URL: settings.ENTERPRISE_ENROLLMENT_API_URL,
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
            validate_email_to_link(email, form_field_value, ValidationMessages.INVALID_EMAIL_OR_USERNAME)
        except ValidationError as exc:
            manage_learners_form.add_error(ManageLearnersForm.Fields.EMAIL_OR_USERNAME, exc.message)
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
                    message = _("Error at line {line}: {message}\n").format(line=index + 1, message=exc.message)
                    errors.append(message)
                else:
                    if already_linked:
                        already_linked_emails.append((email, already_linked.enterprise_customer))
                    elif email in emails:
                        duplicate_emails.append(email)
                    else:
                        emails.add(email)
        except ValidationError as exc:
            errors.append(exc.message)

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
            "{count} new user was linked to {enterprise_customer_name}.",
            "{count} new users were linked to {enterprise_customer_name}.",
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
                _("Some users were already linked to this Enterprise Customer: {list_of_emails}").format(
                    list_of_emails=", ".join(this_customer_linked_emails)
                )
            )
        if other_customer_linked_emails:
            messages.warning(
                request,
                _(
                    "The following learners are already associated with another Enterprise Customer. "
                    "These learners were not added to {enterprise_customer_name}: {list_of_emails}"
                ).format(
                    enterprise_customer_name=enterprise_customer.name,
                    list_of_emails=", ".join(other_customer_linked_emails),
                )
            )
        if duplicate_emails:
            messages.warning(
                request,
                _("Some duplicate emails in the CSV were ignored: {list_of_emails}").format(
                    list_of_emails=", ".join(duplicate_emails)
                )
            )
        # Build a list of all the emails that we can act on further; that is,
        # emails that we either linked to this customer, or that were linked already.
        all_processable_emails = list(emails) + this_customer_linked_emails

        return all_processable_emails

    @classmethod
    def _enroll_users(cls, enterprise_customer, emails, course_id, mode, request, notify=True):
        """
        Enroll the users with the given email addresses to the course specified by course_id.

        Args:
            cls (type): The EnterpriseCustomerManageLearnersView class itself
            enterprise_customer: The instance of EnterpriseCustomer whose attached users we're enrolling
            emails: An iterable of strings containing email addresses to enroll in a course
            course_id: The ID of the course in which we want to enroll
            mode: The enrollment mode the users will be enrolled in the course with
            request: The HTTP request the enrollment is being created by
            notify: Whether to notify (by email) the users that have been enrolled
        """
        enrolled = []
        non_existing = []
        failed = []
        enrollment_client = EnrollmentApiClient()
        course_details = CourseCatalogApiClient(request.user).get_course_run(course_id)

        if notify:
            # Prefetch course metadata for drafting an email if we're going to send a notification
            course_url = course_details.get('marketing_url')
            if course_url is None:
                # If we didn't get a useful path to the course on a marketing site from the catalog API,
                # then we should build a path to the course on the LMS directly.
                course_url = get_reversed_url_by_site(
                    request,
                    enterprise_customer.site,
                    'about_course',
                    args=(course_id,),
                )
            course_name = course_details.get('title')
            course_start = course_details.get('start')

        with ConditionalEmailConnection(open_conn=notify) as email_conn:
            for email in emails:
                try:
                    user = User.objects.get(email=email)
                except User.DoesNotExist:
                    non_existing.append(email)
                    continue
                try:
                    enrollment_client.enroll_user_in_course(user.username, course_id, mode)
                except HttpClientError as exc:
                    failed.append(email)
                    error_message = json.loads(exc.content.decode()).get("message", "No error message provided.")
                    logging.error(
                        "Error while enrolling user %(user)s: %(message)s",
                        dict(user=user.username, message=error_message),
                    )
                else:
                    ecu = EnterpriseCustomerUser.objects.get_link_by_email(email)
                    EnterpriseCourseEnrollment.objects.get_or_create(
                        enterprise_customer_user=ecu,
                        course_id=course_id
                    )
                    enrolled.append(email)
                    if notify:
                        send_email_notification_message(
                            user=user,
                            enrolled_in={
                                'name': course_name,
                                'url': course_url,
                                'type': 'course',
                                'start': parse_lms_api_datetime(course_start),
                            },
                            enterprise_customer=enterprise_customer,
                            email_connection=email_conn,
                        )
        enrolled_count = len(enrolled)
        if enrolled_count:
            messages.success(request, ungettext(
                "{enrolled_count} user was enrolled to {course_id}.",
                "{enrolled_count} users were enrolled to {course_id}.",
                enrolled_count,
            ).format(enrolled_count=enrolled_count, course_id=course_id))
        if non_existing:
            messages.warning(request, _(
                "The following users do not have an account on {}. They have not been enrolled in the course."
                " When these users create an account, they will be enrolled in the course automatically: {}"
            ).format(settings.PLATFORM_NAME, ", ".join(non_existing)))
            for email in non_existing:
                pending_user = PendingEnterpriseCustomerUser.objects.get(
                    enterprise_customer=enterprise_customer,
                    user_email=email
                )
                PendingEnrollment.objects.update_or_create(
                    user=pending_user,
                    course_id=course_id,
                    course_mode=mode
                )
                if notify:
                    send_email_notification_message(
                        user=pending_user,
                        enrolled_in={
                            'name': course_name,
                            'url': course_url,
                            'type': 'course',
                            'start': parse_lms_api_datetime(course_start),
                        },
                        enterprise_customer=enterprise_customer,
                        email_connection=email_conn,
                    )

        if failed:
            messages.error(
                request,
                _("Enrollment of some users failed: {}").format(", ".join(failed)),
            )

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
        manage_learners_form = ManageLearnersForm(user=request.user)
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
        manage_learners_form = ManageLearnersForm(request.POST, request.FILES, user=request.user)

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
            course_ids = []
            course_details = manage_learners_form.cleaned_data.get(ManageLearnersForm.Fields.COURSE)
            program_details = manage_learners_form.cleaned_data.get(ManageLearnersForm.Fields.PROGRAM)

            notification_type = manage_learners_form.cleaned_data.get(ManageLearnersForm.Fields.NOTIFY)
            notify = notification_type == ManageLearnersForm.NotificationTypes.BY_EMAIL

            if course_details:
                course_ids.append(course_details['course_id'])
            elif program_details:

                course_ids.extend(get_course_runs_from_program(program_details))
                program_notify = notify
                notify = False
                if program_notify:
                    program_name = program_details.get('title')
                    program_branding = program_details.get('type')
                    program_url = program_details.get('marketing_url')
                    program_type = 'program'
                    program_start = get_earliest_start_date_from_program(program_details)
                    with ConditionalEmailConnection(program_notify) as email_conn:
                        for email in linked_learners:
                            try:
                                user = User.objects.get(email=email)
                            except User.DoesNotExist:
                                user = PendingEnterpriseCustomerUser.objects.get(
                                    enterprise_customer=enterprise_customer,
                                    user_email=email,
                                )
                            send_email_notification_message(
                                user=user,
                                enrolled_in={
                                    'name': program_name,
                                    'url': program_url,
                                    'type': program_type,
                                    'start': program_start,
                                    'branding': program_branding,
                                },
                                enterprise_customer=enterprise_customer,
                                email_connection=email_conn,
                            )

            if course_ids:
                course_mode = manage_learners_form.cleaned_data[ManageLearnersForm.Fields.COURSE_MODE]
                for course_id in course_ids:
                    self._enroll_users(
                        enterprise_customer,
                        linked_learners,
                        course_id,
                        course_mode,
                        request,
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
            message = _("Email {email} is not linked to Enterprise Customer {ec_name}").format(
                email=email_to_unlink, ec_name=enterprise_customer.name
            )
            return HttpResponse(message, content_type="application/json", status=404)

        return HttpResponse(
            json.dumps({}),
            content_type="application/json"
        )

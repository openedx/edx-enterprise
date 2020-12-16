# -*- coding: utf-8 -*-
"""
Custom Django Admin views used in enterprise app.
"""

import datetime
import logging

from django.conf import settings
from django.contrib import admin, auth, messages
from django.contrib.auth import get_permission_codename
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from django.views.generic import View

from enterprise.admin.forms import (
    ManageLearnersDataSharingConsentForm,
    ManageLearnersForm,
    TransmitEnterpriseCoursesForm,
)
from enterprise.admin.utils import (
    UrlNames,
    email_or_username__to__email,
    paginated_list,
    parse_csv,
    split_usernames_and_emails,
)
from enterprise.api_client.ecommerce import EcommerceApiClient
from enterprise.constants import PAGE_SIZE
from enterprise.models import (
    EnrollmentNotificationEmailTemplate,
    EnterpriseCustomer,
    EnterpriseCustomerUser,
    PendingEnterpriseCustomerUser,
)
from enterprise.utils import (
    ValidationMessages,
    delete_data_sharing_consent,
    enroll_users_in_course,
    get_ecommerce_worker_user,
    validate_course_exists_for_enterprise,
    validate_email_to_link,
)

# Only create manual enrollments if running in edx-platform
try:
    from common.djangoapps.student.api import create_manual_enrollment_audit
except ImportError:
    create_manual_enrollment_audit = None
User = auth.get_user_model()


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


class BaseEnterpriseCustomerView(View):
    """
    Base class for Enterprise Customer views.
    """
    template = None

    @staticmethod
    def _get_admin_context(request, customer):
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

    def _get_view_context(self, request, customer_uuid):
        """
        Return the default context parameters
        """
        return {
            'enterprise_customer': EnterpriseCustomer.objects.get(uuid=customer_uuid)  # pylint: disable=no-member
        }

    def _build_context(self, request, customer_uuid):
        """
        Build common context parts used by different handlers in this view.
        """
        context = self._get_view_context(request, customer_uuid)
        context.update(admin.site.each_context(request))
        context.update(self._get_admin_context(request, context['enterprise_customer']))
        return context

    def get_form_view(self, request, customer_uuid, additional_context=None):
        """
        render the form with appropriate context.
        """
        context = self._build_context(request, customer_uuid)
        context.update(additional_context)
        return render(request, self.template, context)


class EnterpriseCustomerManageLearnerDataSharingConsentView(BaseEnterpriseCustomerView):
    """
    Manage Learners Data Sharing Consent View.

    Allows to request the DSC from a learner for a specific course.
    """
    template = 'enterprise/admin/clear_learners_data_sharing_consent.html'

    class ContextParameters:
        """
        Namespace-style class for custom context parameters.
        """
        ENTERPRISE_CUSTOMER = 'enterprise_customer'
        MANAGE_LEARNERS_DSC_FORM = 'manage_learners_data_sharing_consent_form'

    def get(self, request, customer_uuid):
        """
        Handle GET request - render "Request a DSC from Learner" form.

        Arguments:
            request (django.http.request.HttpRequest): Request instance
            customer_uuid (str): Enterprise Customer UUID

        Returns:
            django.http.response.HttpResponse: HttpResponse
        """
        return self.get_form_view(
            request,
            customer_uuid,
            additional_context={
                self.ContextParameters.MANAGE_LEARNERS_DSC_FORM: ManageLearnersDataSharingConsentForm()
            }
        )

    def post(self, request, customer_uuid):
        """
        Handle POST request - handle form submissions.

        Arguments:
            request (django.http.request.HttpRequest): Request instance
            customer_uuid (str): Enterprise Customer UUID
        """
        manage_learners_dsc_form = ManageLearnersDataSharingConsentForm(
            request.POST,
            enterprise_customer=EnterpriseCustomer.objects.get(uuid=customer_uuid)
        )

        # check that form data is well-formed
        if manage_learners_dsc_form.is_valid():
            delete_data_sharing_consent(
                manage_learners_dsc_form.cleaned_data[ManageLearnersDataSharingConsentForm.Fields.COURSE],
                customer_uuid,
                manage_learners_dsc_form.cleaned_data[ManageLearnersDataSharingConsentForm.Fields.EMAIL_OR_USERNAME]
            )
            messages.success(request, _("Successfully requested the Data Sharing consent from learner."))
            return HttpResponseRedirect(reverse("admin:" + UrlNames.MANAGE_LEARNERS_DSC, args=(customer_uuid,)))

        return self.get_form_view(
            request,
            customer_uuid,
            additional_context={
                self.ContextParameters.MANAGE_LEARNERS_DSC_FORM: manage_learners_dsc_form
            }
        )


class EnterpriseCustomerTransmitCoursesView(BaseEnterpriseCustomerView):
    """
    Transmit courses view.

    Allows transmitting of courses metadata for provided enterprise.
    """
    template = 'enterprise/admin/transmit_courses_metadata.html'

    class ContextParameters:
        """
        Namespace-style class for custom context parameters.
        """
        ENTERPRISE_CUSTOMER = 'enterprise_customer'
        TRANSMIT_COURSES_METADATA_FORM = 'transmit_courses_metadata_form'

    def get(self, request, customer_uuid):
        """
        Handle GET request - render "Transmit courses metadata" form.

        Arguments:
            request (django.http.request.HttpRequest): Request instance
            customer_uuid (str): Enterprise Customer UUID

        Returns:
            django.http.response.HttpResponse: HttpResponse
        """
        return self.get_form_view(
            request,
            customer_uuid,
            additional_context={
                self.ContextParameters.TRANSMIT_COURSES_METADATA_FORM: TransmitEnterpriseCoursesForm()
            }
        )

    def post(self, request, customer_uuid):
        """
        Handle POST request - handle form submissions.

        Arguments:
            request (django.http.request.HttpRequest): Request instance
            customer_uuid (str): Enterprise Customer UUID
        """
        transmit_courses_metadata_form = TransmitEnterpriseCoursesForm(request.POST)

        # check that form data is well-formed
        if transmit_courses_metadata_form.is_valid():
            channel_worker_username = transmit_courses_metadata_form.cleaned_data['channel_worker_username']

            # call `transmit_content_metadata` management command to trigger
            # transmission of enterprise courses metadata
            call_command(
                'transmit_content_metadata',
                '--catalog_user', channel_worker_username,
                enterprise_customer=customer_uuid
            )

            # Redirect to GET
            return HttpResponseRedirect('')

        return self.get_form_view(
            request,
            customer_uuid,
            additional_context={
                self.ContextParameters.TRANSMIT_COURSES_METADATA_FORM: transmit_courses_metadata_form
            }
        )


class EnterpriseCustomerManageLearnersView(BaseEnterpriseCustomerView):
    """
    Manage Learners view.

    Lists learners linked to chosen Enterprise Customer and allows adding and deleting them.
    """
    template = "enterprise/admin/manage_learners.html"

    class ContextParameters:
        """
        Namespace-style class for custom context parameters.
        """
        ENTERPRISE_CUSTOMER = "enterprise_customer"
        LEARNERS = "learners"
        PENDING_LEARNERS = "pending_learners"
        MANAGE_LEARNERS_FORM = "manage_learners_form"
        SEARCH_KEYWORD = "search_keyword"
        ENROLLMENT_URL = 'ENROLLMENT_API_ROOT_URL'

    def _get_view_context(self, request, customer_uuid):
        enterprise_customer = EnterpriseCustomer.objects.get(uuid=customer_uuid)  # pylint: disable=no-member
        search_keyword = self.get_search_keyword(request)
        linked_learners = self.get_enterprise_customer_user_queryset(request, search_keyword, customer_uuid)
        pending_linked_learners = self.get_pending_users_queryset(search_keyword, customer_uuid)

        context = {
            self.ContextParameters.ENTERPRISE_CUSTOMER: enterprise_customer,
            self.ContextParameters.PENDING_LEARNERS: pending_linked_learners,
            self.ContextParameters.LEARNERS: linked_learners,
            self.ContextParameters.SEARCH_KEYWORD: search_keyword or '',
            self.ContextParameters.ENROLLMENT_URL: settings.LMS_ENROLLMENT_API_PATH,
        }
        return context

    def get_search_keyword(self, request):
        """
        Retrieve the search querystring from the GET parameters.
        """
        return request.GET.get('q', None)

    def get_enterprise_customer_user_queryset(self, request, search_keyword, customer_uuid, page_size=PAGE_SIZE):
        """
        Get the list of EnterpriseCustomerUsers we want to render.

        Arguments:
            request (HttpRequest): HTTP Request instance.
            search_keyword (str): The keyword to search for in users' email addresses and usernames.
            customer_uuid (str): A unique identifier to filter down to only users linked to a
            particular EnterpriseCustomer.
            page_size (int): Number of learners displayed in each paginated set.
        """
        page = request.GET.get('page', 1)
        learners = EnterpriseCustomerUser.objects.filter(enterprise_customer__uuid=customer_uuid)
        user_ids = learners.values_list('user_id', flat=True)
        matching_users = User.objects.filter(pk__in=user_ids)
        if search_keyword is not None:
            matching_users = matching_users.filter(
                Q(email__icontains=search_keyword) | Q(username__icontains=search_keyword)
            )
        matching_user_ids = matching_users.values_list('pk', flat=True)
        learners = learners.filter(user_id__in=matching_user_ids)
        return paginated_list(learners, page, page_size)

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
    def _handle_singular(cls, request, enterprise_customer, manage_learners_form):
        """
        Link single user by email or username.

        Arguments:
            enterprise_customer (EnterpriseCustomer): learners will be linked to this Enterprise Customer instance
            manage_learners_form (ManageLearnersForm): bound ManageLearners form instance
        """
        form_field_value = manage_learners_form.cleaned_data[ManageLearnersForm.Fields.EMAIL_OR_USERNAME]
        email = email_or_username__to__email(form_field_value)
        try:
            existing_record = validate_email_to_link(email, form_field_value, ValidationMessages.
                                                     INVALID_EMAIL_OR_USERNAME, True)
        except ValidationError as exc:
            manage_learners_form.add_error(ManageLearnersForm.Fields.EMAIL_OR_USERNAME, exc)
        else:
            if isinstance(existing_record, PendingEnterpriseCustomerUser) and existing_record.enterprise_customer \
                    != enterprise_customer:
                messages.warning(
                    request,
                    ValidationMessages.PENDING_USER_ALREADY_LINKED.format(
                        user_email=email,
                        ec_name=existing_record.enterprise_customer.name
                    )
                )
                return None
            EnterpriseCustomerUser.objects.link_user(enterprise_customer, email)
            return [email]

    def _handle_bulk_upload_errors(self, manage_learners_form, errors):
        """
        Handles adding errors to the ``manager_learners_form``.

        Arguments:
            manage_learners_form (ManageLearnersForm): bound ManageLearners form instance
            errors (list): List of validation errors from parsing the uploaded CSV.
        """
        manage_learners_form.add_error(
            ManageLearnersForm.Fields.GENERAL_ERRORS, ValidationMessages.BULK_LINK_FAILED
        )
        for error in errors:
            manage_learners_form.add_error(ManageLearnersForm.Fields.BULK_UPLOAD, error)

    def _process_bulk_upload_data(
            self,
            request,
            enterprise_customer,
            emails,
            already_linked_emails,
            duplicate_emails,
    ):
        """
        Processes the parsed data from bulk csv upload, adding the appropriate success and warning messages.

        Arguments:
            request: A request instance
            enterprise_customer (EnterpriseCustomer): An instance of an EnterpriseCustomer record.
            emails (list): List of valid, non-duplicate emails.
            already_linked_emails (list): List of emails that are already linked with the EnterpriseCustomer.
            duplicate_emails (list): List of emails that are duplicate entries.

        Returns: List of processable email addresses.
        """
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
        course_id_with_emails = {}
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
                course_id = row.get(ManageLearnersForm.CsvColumns.COURSE_ID, None)  # optional column
                course_details = None
                try:
                    already_linked = validate_email_to_link(email, ignore_existing=True)
                    if course_id:
                        course_details = validate_course_exists_for_enterprise(enterprise_customer, course_id)
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

                    # course column exists for row, is a valid course id, and exists in the enterprise's catalog(s).
                    if course_details:
                        if course_details['course_id'] not in course_id_with_emails:
                            course_id_with_emails[course_details['course_id']] = {email}
                        else:
                            course_id_with_emails[course_details['course_id']].add(email)
        except ValidationError as exc:
            errors.append(exc)

        if errors:
            cls._handle_bulk_upload_errors(cls, manage_learners_form=manage_learners_form, errors=errors)
            # There were validation errors, so prevent any further action.
            return [], {}

        # There were no errors. Now do the actual linking:
        for email in emails:
            EnterpriseCustomerUser.objects.link_user(enterprise_customer, email)

        # Process the bulk uploaded data:
        processable_emails = cls._process_bulk_upload_data(
            cls,
            request=request,
            enterprise_customer=enterprise_customer,
            emails=emails,
            already_linked_emails=already_linked_emails,
            duplicate_emails=duplicate_emails,
        )
        return processable_emails, course_id_with_emails

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
    def get_success_enrollment_message(cls, users, enrolled_in):
        """
        Create message for the users who were enrolled in a course.

        Args:
            users: An iterable of users who were successfully enrolled
            enrolled_in (str): A string identifier for the course the users were enrolled in

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
        Create message for the users who were not able to be enrolled in a course.

        Args:
            users: An iterable of users who were not successfully enrolled
            enrolled_in (str): A string identifier for the course with which enrollment was attempted

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
        Create message for the users who were enrolled in a course.

        Args:
            users: An iterable of PendingEnterpriseCustomerUsers who were successfully linked with a pending enrollment
            enrolled_in (str): A string identifier for the course the pending users were linked to

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
            notify=True,
            enrollment_reason=None,
            sales_force_id=None,
            discount=0.0
    ):
        """
        Enroll the users with the given email addresses to the course.

        Args:
            cls (type): The EnterpriseCustomerManageLearnersView class itself
            request: The HTTP request the enrollment is being created by
            enterprise_customer: The instance of EnterpriseCustomer whose attached users we're enrolling
            emails: An iterable of strings containing email addresses to enroll in a course
            mode: The enrollment mode the users will be enrolled in the course with
            course_id: The ID of the course in which we want to enroll
            notify: Whether to notify (by email) the users that have been enrolled
        """
        pending_messages = []
        paid_modes = ['verified', 'professional']

        succeeded, pending, failed = enroll_users_in_course(
            enterprise_customer=enterprise_customer,
            course_id=course_id,
            course_mode=mode,
            emails=sorted(emails),
            enrollment_requester=request.user,
            enrollment_reason=enrollment_reason,
            discount=discount,
            sales_force_id=sales_force_id,
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

        if mode in paid_modes:
            # Create an order to track the manual enrollments of non-pending accounts
            enrollments = [{
                "lms_user_id": success.id,
                "email": success.email,
                "username": success.username,
                "course_run_key": course_id,
                "discount_percentage": float(discount),
                "enterprise_customer_name": enterprise_customer.name,
                "enterprise_customer_uuid": str(enterprise_customer.uuid),
                "mode": mode,
                "sales_force_id": sales_force_id,
            } for success in succeeded]
            EcommerceApiClient(get_ecommerce_worker_user()).create_manual_enrollment_orders(enrollments)
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
        enterprise_customer = EnterpriseCustomer.objects.get(uuid=customer_uuid)  # pylint: disable=no-member
        manage_learners_form = ManageLearnersForm(user=request.user, enterprise_customer=enterprise_customer)

        return self.get_form_view(
            request,
            customer_uuid,
            additional_context={
                self.ContextParameters.MANAGE_LEARNERS_FORM: manage_learners_form
            }
        )

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
        course_id_with_emails = {}

        # initial form validation - check that form data is well-formed
        if manage_learners_form.is_valid():
            email_field_as_bulk_input = split_usernames_and_emails(
                manage_learners_form.cleaned_data[ManageLearnersForm.Fields.EMAIL_OR_USERNAME]
            )
            is_bulk_entry = len(email_field_as_bulk_input) > 1
            # The form is valid. Call the appropriate helper depending on the mode:
            mode = manage_learners_form.cleaned_data[ManageLearnersForm.Fields.MODE]
            if mode == ManageLearnersForm.Modes.MODE_SINGULAR and not is_bulk_entry:
                linked_learners = self._handle_singular(request, enterprise_customer, manage_learners_form)
            elif mode == ManageLearnersForm.Modes.MODE_SINGULAR:
                linked_learners, __ = self._handle_bulk_upload(
                    enterprise_customer,
                    manage_learners_form,
                    request,
                    email_list=email_field_as_bulk_input
                )
            else:
                linked_learners, course_id_with_emails = self._handle_bulk_upload(
                    enterprise_customer,
                    manage_learners_form,
                    request,
                )

        # _handle_form might add form errors, so we check if it is still valid
        if manage_learners_form.is_valid():
            # If we aren't installed in Open edX, blank out enrollment reason so downstream methods don't attempt to
            # create audit items
            if create_manual_enrollment_audit is not None:
                manual_enrollment_reason = manage_learners_form.cleaned_data.get(ManageLearnersForm.Fields.REASON)
            else:
                manual_enrollment_reason = None
                logging.exception(
                    "To create enrollment audits for enterprise learners, "
                    "this package must be installed in an Open edX environment."
                )

            notification_type = manage_learners_form.cleaned_data.get(ManageLearnersForm.Fields.NOTIFY)
            notify = notification_type == ManageLearnersForm.NotificationTypes.BY_EMAIL
            discount = manage_learners_form.cleaned_data.get(ManageLearnersForm.Fields.DISCOUNT)
            sales_force_id = manage_learners_form.cleaned_data.get(ManageLearnersForm.Fields.SALES_FORCE_ID)
            course_mode = manage_learners_form.cleaned_data.get(ManageLearnersForm.Fields.COURSE_MODE)
            course_id = None

            if not course_id_with_emails:
                course_details = manage_learners_form.cleaned_data.get(ManageLearnersForm.Fields.COURSE) or {}
                course_id = course_details.get('course_id')
                if course_id and linked_learners:
                    self._enroll_users(
                        request=request,
                        enterprise_customer=enterprise_customer,
                        emails=linked_learners,
                        mode=course_mode,
                        course_id=course_id,
                        notify=notify,
                        enrollment_reason=manual_enrollment_reason,
                        sales_force_id=sales_force_id,
                        discount=discount
                    )
            else:
                for course_id in course_id_with_emails:
                    emails_to_enroll = course_id_with_emails[course_id]
                    if emails_to_enroll:
                        self._enroll_users(
                            request=request,
                            enterprise_customer=enterprise_customer,
                            emails=list(emails_to_enroll),
                            mode=course_mode,
                            course_id=course_id,
                            notify=notify,
                            enrollment_reason=manual_enrollment_reason,
                            sales_force_id=sales_force_id,
                            discount=discount
                        )

            # Redirect to GET if everything went smooth.
            manage_learners_url = reverse("admin:" + UrlNames.MANAGE_LEARNERS, args=(customer_uuid,))
            search_keyword = self.get_search_keyword(request)
            if search_keyword:
                manage_learners_url = manage_learners_url + "?q=" + search_keyword
            return HttpResponseRedirect(manage_learners_url)

        # if something went wrong - display bound form on the page
        return self.get_form_view(
            request,
            customer_uuid,
            additional_context={
                self.ContextParameters.MANAGE_LEARNERS_FORM: manage_learners_form
            }
        )

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
            # pylint: disable=http-response-with-content-type-json
            return HttpResponse(message, content_type="application/json", status=404)

        return JsonResponse({})

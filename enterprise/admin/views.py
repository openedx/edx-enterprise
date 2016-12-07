"""
Custom Django Admin views used in enterprise app.
"""
from __future__ import absolute_import, unicode_literals

import json
import logging

from edx_rest_api_client.exceptions import HttpClientError

from django.contrib import admin, messages
from django.contrib.auth import get_permission_codename
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from django.views.generic import View

from enterprise.admin.forms import ManageLearnersForm
from enterprise.admin.utils import ValidationMessages, email_or_username__to__email, parse_csv, validate_email_to_link
from enterprise.enrollment_api import enroll_user_in_course
from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser, PendingEnterpriseCustomerUser

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


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
        linked_learners = EnterpriseCustomerUser.objects.filter(enterprise_customer__uuid=enterprise_customer.uuid)
        pending_linked_learners = PendingEnterpriseCustomerUser.objects.filter(
            enterprise_customer__uuid=enterprise_customer.uuid
        )

        context = {
            self.ContextParameters.ENTERPRISE_CUSTOMER: enterprise_customer,
            self.ContextParameters.PENDING_LEARNERS: pending_linked_learners,
            self.ContextParameters.LEARNERS: linked_learners,
        }
        context.update(admin.site.each_context(request))
        context.update(self._build_admin_context(request, enterprise_customer))
        return context

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
    def _handle_bulk_upload(cls, enterprise_customer, manage_learners_form, request):
        """
        Bulk link users by email.

        Arguments:
            enterprise_customer (EnterpriseCustomer): learners will be linked to this Enterprise Customer instance
            manage_learners_form (ManageLearnersForm): bound ManageLearners form instance
            request (django.http.request.HttpRequest): HTTP Request instance
        """
        errors = []
        emails = set()
        already_linked_emails = []
        duplicate_emails = []
        csv_file = manage_learners_form.cleaned_data[ManageLearnersForm.Fields.BULK_UPLOAD]
        try:
            parsed_csv = parse_csv(csv_file, expected_columns={ManageLearnersForm.CsvColumns.EMAIL})
            for index, row in enumerate(parsed_csv):
                email = row[ManageLearnersForm.CsvColumns.EMAIL]
                try:
                    already_linked = validate_email_to_link(email, ignore_existing=True)
                except ValidationError as exc:
                    message = _("Error at line {line}: {message}\n").format(line=index + 1, message=exc.message)
                    errors.append(message)
                else:
                    if already_linked:
                        already_linked_emails.append(email)
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
        if already_linked_emails:
            messages.warning(
                request,
                _("Some users were already linked to this Enterprise Customer: {list_of_emails}").format(
                    list_of_emails=", ".join(already_linked_emails)
                )
            )
        if duplicate_emails:
            messages.warning(
                request,
                _("Some duplicate emails in the CSV were ignored: {list_of_emails}").format(
                    list_of_emails=", ".join(duplicate_emails)
                )
            )
        return list(emails) + already_linked_emails

    @classmethod
    def _enroll_users(cls, emails, course_details, mode, request):
        """
        Enroll the users with the given email addresses to the course specified by course_details.
        """
        enrolled = []
        non_existing = []
        failed = []
        for email in emails:
            try:
                username = User.objects.get(email=email).username
            except User.DoesNotExist:
                non_existing.append(email)
                continue
            try:
                enroll_user_in_course(username, course_details, mode)
            except HttpClientError as exc:
                failed.append(email)
                error_message = json.loads(exc.content.decode()).get("message", "No error message provided.")
                logging.error(
                    "Error while enrolling user %(user)s: %(message)s",
                    dict(user=username, message=error_message),
                )
            else:
                enrolled.append(email)
        enrolled_count = len(enrolled)
        if enrolled_count:
            course_id = course_details["course_id"]
            messages.success(request, ungettext(
                "{enrolled_count} user was enrolled to {course_id}.",
                "{enrolled_count} users were enrolled to {course_id}.",
                enrolled_count,
            ).format(enrolled_count=enrolled_count, course_id=course_id))
        if non_existing:
            messages.warning(request, _(
                "The following users do not have accounts yet and were not enrolled: {}"
            ).format(", ".join(non_existing)))
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
        manage_learners_form = ManageLearnersForm()
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
        manage_learners_form = ManageLearnersForm(request.POST, request.FILES)

        # initial form validation - check that form data is well-formed
        if manage_learners_form.is_valid():
            # The form is valid. Call the appropriate helper depending on the mode:
            mode = manage_learners_form.cleaned_data[ManageLearnersForm.Fields.MODE]
            if mode == ManageLearnersForm.Modes.MODE_SINGULAR:
                linked_learners = self._handle_singular(enterprise_customer, manage_learners_form)
            else:
                linked_learners = self._handle_bulk_upload(enterprise_customer, manage_learners_form, request)

        # _handle_form might add form errors, so we check if it is still valid
        if manage_learners_form.is_valid():

            # Enroll linked users in a course if requested
            course_details = manage_learners_form.cleaned_data.get(ManageLearnersForm.Fields.COURSE)
            if course_details:
                course_mode = manage_learners_form.cleaned_data[ManageLearnersForm.Fields.COURSE_MODE]
                self._enroll_users(linked_learners, course_details, course_mode, request)

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

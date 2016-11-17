"""
Custom Django Admin views used in enterprise app.
"""
from __future__ import absolute_import, unicode_literals

import json

from django.contrib import admin
from django.contrib.auth import get_permission_codename
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import ugettext as _
from django.views.generic import View

from enterprise.admin.forms import ManageLearnersForm
from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser, PendingEnterpriseCustomerUser


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
        # TODO: bulk upload
        enterprise_customer = EnterpriseCustomer.objects.get(uuid=customer_uuid)  # pylint: disable=no-member
        manage_learners_form = ManageLearnersForm(request.POST)
        if manage_learners_form.is_valid():
            EnterpriseCustomerUser.objects.link_user(enterprise_customer, manage_learners_form.cleaned_data["email"])
            manage_learners_form = ManageLearnersForm()

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

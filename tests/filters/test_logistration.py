"""
Tests for enterprise.filters.logistration pipeline steps.
"""
from unittest.mock import MagicMock, patch

import ddt
from openedx_filters.learning.filters import LogistrationMFERedirectRequested

from django.test import RequestFactory, TestCase

from enterprise.filters.logistration import (
    EnterpriseMFERedirectVeto,
    LoginFormEnterpriseOverrides,
    LogistrationContextEnricher,
    LogistrationCookieSetter,
    PostLoginEnterpriseRedirect,
    RegistrationFormEnterpriseOverrides,
)


def _make_request():
    return RequestFactory().get('/')


def _learner_data(*uuids):
    """
    Build a get_enterprise_learner_data_from_api response for the given enterprise uuids.
    """
    return [{'enterprise_customer': {'uuid': uuid}} for uuid in uuids]


@ddt.ddt
class TestLogistrationContextEnricher(TestCase):
    """
    Tests for the LogistrationContextEnricher pipeline step.
    """

    def _make_step(self):
        return LogistrationContextEnricher('org.openedx.learning.logistration.context.requested.v1', [])

    @ddt.data(
        {'enterprise_customer': {'uuid': 'some-uuid', 'name': 'Acme'}, 'expected_enabled': True},
        {'enterprise_customer': None, 'expected_enabled': False},
    )
    @ddt.unpack
    @patch('enterprise.filters.logistration.get_current_request')
    @patch('enterprise.filters.logistration.get_enterprise_slug_login_url', return_value='/enterprise/login')
    @patch('enterprise.filters.logistration.update_logistration_context_for_enterprise')
    @patch('enterprise.filters.logistration.enterprise_enabled')
    @patch('enterprise.filters.logistration.enterprise_customer_for_request')
    def test_context_updated_unconditionally(
            self, mock_ecfr, mock_enabled, mock_update, mock_slug_url, mock_get_current_request,
            enterprise_customer, expected_enabled,
    ):
        """
        The context update and data keys are applied with or without an enterprise customer,
        matching the original platform behavior (e.g. enable_enterprise_sidebar=False and the
        third-party-auth error message adjustments also apply to non-enterprise requests).
        """
        mock_ecfr.return_value = enterprise_customer
        mock_enabled.return_value = expected_enabled
        request = _make_request()
        mock_get_current_request.return_value = request
        context = {'data': {}}

        step = self._make_step()
        result = step.run_filter(context=context)

        mock_update.assert_called_once_with(request, context, enterprise_customer)
        assert result['context']['data']['enterprise_slug_login_url'] == '/enterprise/login'
        assert result['context']['data']['is_enterprise_enable'] is expected_enabled
        assert mock_slug_url.call_count == 1

    @patch('enterprise.filters.logistration.get_current_request')
    @patch('enterprise.filters.logistration.get_enterprise_slug_login_url', return_value='/enterprise/login')
    @patch('enterprise.filters.logistration.update_logistration_context_for_enterprise')
    @patch('enterprise.filters.logistration.enterprise_enabled', return_value=True)
    @patch('enterprise.filters.logistration.enterprise_customer_for_request', return_value=None)
    def test_context_without_data_key(
            self, _mock_ecfr, _mock_enabled, mock_update, _mock_slug_url, mock_get_current_request,
    ):
        """
        A context without a 'data' key is updated without raising and without adding the key.
        """
        request = _make_request()
        mock_get_current_request.return_value = request
        context = {}

        step = self._make_step()
        result = step.run_filter(context=context)

        mock_update.assert_called_once_with(request, context, None)
        assert 'data' not in result['context']


class TestLogistrationCookieSetter(TestCase):
    """
    Tests for the LogistrationCookieSetter pipeline step.
    """

    @patch('enterprise.filters.logistration.get_current_request')
    @patch('enterprise.filters.logistration.handle_enterprise_cookies_for_logistration')
    def test_cookies_handled_unconditionally(self, mock_handle_cookies, mock_get_current_request):
        """
        Enterprise cookie handling is applied to every logistration response and all
        inputs are returned unchanged.
        """
        request = _make_request()
        mock_get_current_request.return_value = request
        response = MagicMock()
        context = {'enable_enterprise_sidebar': False}

        step = LogistrationCookieSetter('org.openedx.learning.logistration.response.rendered.v1', [])
        result = step.run_filter(response=response, context=context)

        mock_handle_cookies.assert_called_once_with(request, response, context)
        assert result['response'] is response
        assert result['context'] is context


@ddt.ddt
class TestLoginFormEnterpriseOverrides(TestCase):
    """
    Tests for the LoginFormEnterpriseOverrides pipeline step.
    """

    def _make_step(self):
        return LoginFormEnterpriseOverrides('org.openedx.learning.login.form.tpa_overrides.requested.v1', [])

    @patch('enterprise.filters.logistration.enterprise_customer_for_request', return_value={'uuid': 'some-uuid'})
    def test_email_overridden_readonly(self, _mock_ecfr):
        """
        With a provider and an enterprise customer, the email field is pre-filled from the
        provider details and made read-only.
        """
        running_pipeline = {'kwargs': {'details': {'email': 'learner@example.com'}}}
        current_provider = MagicMock()
        form_desc = MagicMock()

        step = self._make_step()
        result = step.run_filter(
            form_desc=form_desc,
            running_pipeline=running_pipeline,
            current_provider=current_provider,
        )

        form_desc.override_field_properties.assert_called_once_with(
            'email',
            default='learner@example.com',
            restrictions={'readonly': 'readonly'},
        )
        assert result['form_desc'] is form_desc
        assert result['running_pipeline'] is running_pipeline
        assert result['current_provider'] is current_provider

    @patch('enterprise.filters.logistration.accounts')
    @patch('enterprise.filters.logistration.enterprise_customer_for_request', return_value={'uuid': 'some-uuid'})
    def test_email_overridden_with_length_restrictions(self, _mock_ecfr, mock_accounts):
        """
        Without an email in the provider details, the email field keeps min/max length
        restrictions instead of becoming read-only.
        """
        mock_accounts.EMAIL_MIN_LENGTH = 3
        mock_accounts.EMAIL_MAX_LENGTH = 254
        form_desc = MagicMock()

        step = self._make_step()
        step.run_filter(
            form_desc=form_desc,
            running_pipeline={'kwargs': {'details': {}}},
            current_provider=MagicMock(),
        )

        form_desc.override_field_properties.assert_called_once_with(
            'email',
            default='',
            restrictions={'min_length': 3, 'max_length': 254},
        )

    @ddt.data(
        {'has_provider': False, 'has_customer': True},
        {'has_provider': True, 'has_customer': False},
    )
    @ddt.unpack
    @patch('enterprise.filters.logistration.enterprise_customer_for_request')
    def test_noop_without_provider_or_customer(self, mock_ecfr, has_provider, has_customer):
        """
        The form description is returned unchanged without a current provider or without
        an enterprise customer.
        """
        mock_ecfr.return_value = {'uuid': 'some-uuid'} if has_customer else None
        form_desc = MagicMock()

        step = self._make_step()
        result = step.run_filter(
            form_desc=form_desc,
            running_pipeline={'kwargs': {'details': {'email': 'learner@example.com'}}},
            current_provider=MagicMock() if has_provider else None,
        )

        form_desc.override_field_properties.assert_not_called()
        assert result['form_desc'] is form_desc


@ddt.ddt
class TestRegistrationFormEnterpriseOverrides(TestCase):
    """
    Tests for the RegistrationFormEnterpriseOverrides pipeline step.
    """

    def _make_step(self):
        return RegistrationFormEnterpriseOverrides(
            'org.openedx.learning.registration.form.tpa_overrides.requested.v1', [],
        )

    def _make_provider(self, field_overrides, skip_registration_form=True, skip_optional_checkboxes=False):
        """
        Build a mock third-party-auth provider with registration form data.
        """
        provider = MagicMock()
        provider.skip_registration_form = skip_registration_form
        provider.skip_registration_optional_checkboxes = skip_optional_checkboxes
        provider.get_register_form_data.return_value = field_overrides
        return provider

    @patch('enterprise.filters.logistration.enterprise_customer_for_request', return_value={'uuid': 'some-uuid'})
    def test_fields_hidden_except_tos(self, _mock_ecfr):
        """
        Provider-prefilled fields are hidden except terms of service and honor code; fields
        with falsy override values are skipped.
        """
        provider = self._make_provider({
            'email': 'learner@example.com',
            'name': 'Learner',
            'username': '',
            'honor_code': True,
            'terms_of_service': True,
        })
        form_desc = MagicMock()

        step = self._make_step()
        step.run_filter(
            form_desc=form_desc,
            running_pipeline={'kwargs': {}},
            current_provider=provider,
        )

        hidden_fields = {
            call.args[0] for call in form_desc.override_field_properties.call_args_list
        }
        assert hidden_fields == {'email', 'name'}
        form_desc.override_field_properties.assert_any_call(
            'email',
            field_type='hidden',
            default='learner@example.com',
            label='',
            instructions='',
        )

    @ddt.data(
        {'skip_optional_checkboxes': True, 'expected_hidden': False},
        {'skip_optional_checkboxes': False, 'expected_hidden': True},
    )
    @ddt.unpack
    @patch('enterprise.filters.logistration.enterprise_customer_for_request', return_value={'uuid': 'some-uuid'})
    def test_marketing_emails_opt_in_guard(self, _mock_ecfr, skip_optional_checkboxes, expected_hidden):
        """
        The marketing_emails_opt_in field is not hidden when the SAML provider config has
        skip_registration_optional_checkboxes enabled.
        """
        provider = self._make_provider(
            {'marketing_emails_opt_in': 'true'},
            skip_optional_checkboxes=skip_optional_checkboxes,
        )
        form_desc = MagicMock()

        step = self._make_step()
        step.run_filter(
            form_desc=form_desc,
            running_pipeline={'kwargs': {}},
            current_provider=provider,
        )

        assert form_desc.override_field_properties.called is expected_hidden

    @ddt.data(
        {'skip_registration_form': False, 'has_customer': True},
        {'skip_registration_form': True, 'has_customer': False},
    )
    @ddt.unpack
    @patch('enterprise.filters.logistration.enterprise_customer_for_request')
    def test_noop_without_skip_flag_or_customer(self, mock_ecfr, skip_registration_form, has_customer):
        """
        The form description is returned unchanged when the provider does not skip the
        registration form or the request has no enterprise customer.
        """
        provider = self._make_provider(
            {'email': 'learner@example.com'},
            skip_registration_form=skip_registration_form,
        )
        mock_ecfr.return_value = {'uuid': 'some-uuid'} if has_customer else None
        form_desc = MagicMock()

        step = self._make_step()
        result = step.run_filter(
            form_desc=form_desc,
            running_pipeline={'kwargs': {}},
            current_provider=provider,
        )

        form_desc.override_field_properties.assert_not_called()
        assert result['form_desc'] is form_desc


class TestEnterpriseMFERedirectVeto(TestCase):
    """
    Tests for the EnterpriseMFERedirectVeto pipeline step.
    """

    def _make_step(self):
        return EnterpriseMFERedirectVeto('org.openedx.learning.logistration.mfe.redirect.requested.v1', [])

    @patch('enterprise.filters.logistration.enterprise_customer_for_request', return_value={'uuid': 'some-uuid'})
    def test_prevents_redirect_for_enterprise_customer(self, _mock_ecfr):
        """
        PreventRedirect is raised when the request is associated with an enterprise customer.
        """
        step = self._make_step()

        with self.assertRaises(LogistrationMFERedirectRequested.PreventRedirect):
            step.run_filter(request=_make_request())

    @patch('enterprise.filters.logistration.enterprise_customer_for_request', return_value=None)
    def test_noop_without_enterprise_customer(self, _mock_ecfr):
        """
        The request is returned unchanged without an enterprise customer.
        """
        request = _make_request()

        step = self._make_step()
        result = step.run_filter(request=request)

        assert result['request'] is request


@ddt.ddt
class TestPostLoginEnterpriseRedirect(TestCase):
    """
    Tests for the PostLoginEnterpriseRedirect pipeline step.
    """

    def _make_step(self):
        return PostLoginEnterpriseRedirect('org.openedx.learning.auth.post_login.redirect_url.requested.v1', [])

    def _make_user(self):
        user = MagicMock()
        user.id = 42
        return user

    @ddt.data(
        {'learner_data': []},
        {'learner_data': _learner_data('uuid-1')},
    )
    @ddt.unpack
    @patch('enterprise.filters.logistration.get_enterprise_learner_data_from_api')
    def test_redirect_unchanged_without_multiple_enterprises(self, mock_learner_data, learner_data):
        """
        The redirect URL is returned unchanged when the user is linked to fewer than two
        enterprises.
        """
        mock_learner_data.return_value = learner_data

        step = self._make_step()
        result = step.run_filter(redirect_url='/dashboard', user=self._make_user(), next_url='/dashboard')

        assert result['redirect_url'] == '/dashboard'

    @patch(
        'enterprise.filters.logistration.get_enterprise_learner_data_from_api',
        return_value=_learner_data('uuid-1', 'uuid-2'),
    )
    def test_multiple_enterprises_redirects_to_selection_page(self, _mock_learner_data):
        """
        The redirect URL points at the enterprise selection page, with the next URL quoted
        into success_url, when the user is linked to multiple enterprises.
        """
        step = self._make_step()
        result = step.run_filter(redirect_url='/dashboard', user=self._make_user(), next_url='/dashboard')

        assert result['redirect_url'] == '/enterprise/select/active/?success_url=/dashboard'

    @ddt.data(
        {'is_activated': True},
        {'is_activated': False},
    )
    @ddt.unpack
    @patch('enterprise.filters.logistration.get_current_request')
    @patch('enterprise.filters.logistration.activate_learner_enterprise')
    @patch('enterprise.filters.logistration.get_enterprise_learner_data_from_api')
    def test_enterprise_enrollment_url_bypasses_selection_page(
            self, mock_learner_data, mock_activate, mock_get_current_request, is_activated,
    ):
        """
        When the next URL is a direct enrollment URL for one of the user's enterprises, that
        enterprise is activated and, on success, the selection page is bypassed.
        """
        enterprise_uuid = '99999999-9999-4999-9999-999999999999'
        mock_learner_data.return_value = _learner_data(enterprise_uuid, 'uuid-2')
        mock_activate.return_value = is_activated
        request = _make_request()
        mock_get_current_request.return_value = request
        user = self._make_user()
        next_url = f'/enterprise/{enterprise_uuid}/course/course-v1:testX+test101+2T2020/enroll/'

        step = self._make_step()
        result = step.run_filter(redirect_url=next_url, user=user, next_url=next_url)

        mock_activate.assert_called_once_with(request, user, enterprise_uuid)
        if is_activated:
            assert result['redirect_url'] == next_url
        else:
            assert result['redirect_url'].startswith('/enterprise/select/active/?success_url=')

    @patch(
        'enterprise.filters.logistration.get_enterprise_learner_data_from_api',
        side_effect=RuntimeError('API unavailable'),
    )
    def test_learner_data_api_error_propagates(self, _mock_learner_data):
        """
        Errors from the enterprise learner data API propagate, matching the original
        platform behavior.
        """
        step = self._make_step()

        with self.assertRaises(RuntimeError):
            step.run_filter(redirect_url='/dashboard', user=self._make_user(), next_url='/dashboard')

#!/usr/bin/env bash
#
# Provision devstack fixtures for integration-testing the six openedx-filter
# pipeline steps added in ticket ENT-11568, and print a manual test plan.
#
# To run this script:
#
#     [devstack]       make dev.up.lms+enterprise-catalog+frontend-app-authn
#     [edx-enterprise] make dev.provision.keycloak
#     [edx-enterprise] ./scripts/provision-integration-test-ENT-11568.sh

set -eu -o pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Per-tenant SSO usernames come from the single source of truth that the Keycloak
# realm import and provision-tpa.py also use: keycloak-devstack.env.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "${REPO_ROOT}/keycloak-devstack.env"

set -x

# A learner linked to BOTH enterprises, to trigger the multi-enterprise selection page.
DUAL_LEARNER="dual_enterprise_learner"

LMS_BASE="http://localhost:18000"
# The authn micro-frontend base URL (settings.AUTHN_MICROFRONTEND_URL).
AUTHN_MFE_BASE="http://localhost:1999"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

lms_manage() {
    docker exec -i edx.devstack.lms python manage.py lms --settings devstack "$@"
}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# A learner linked to both enterprises; the first --enterprise-name is the "active" one.
lms_manage create_enterprise_linked_learner \
    --username "$DUAL_LEARNER" \
    --enterprise-name "$GRYFFINDOR_ENTERPRISE_NAME" \
    --enterprise-name "$SLYTHERIN_ENTERPRISE_NAME"

# Read back the Gryffindor UUID for test 11's ?enterprise_customer=<uuid>. Best-effort.
GRYFFINDOR_UUID="$(lms_manage shell -c \
    "from enterprise.models import EnterpriseCustomer; print(EnterpriseCustomer.objects.get(slug='${GRYFFINDOR_REALM}').uuid)" \
    2>/dev/null | grep -ioE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -n1 || true)"

# ---------------------------------------------------------------------------
# Preflight: all six pipeline steps must be registered
# ---------------------------------------------------------------------------
# Fails if plugin_settings did not inject the mappings (usually a missing
# ENABLE_ENTERPRISE_INTEGRATION in lms.yml, or edx-enterprise not installed
# editable in the LMS container).

lms_manage shell -c "
from django.conf import settings
config = getattr(settings, 'OPEN_EDX_FILTERS_CONFIG', {})
found = {k: v['pipeline'] for k, v in sorted(config.items()) if k.startswith('org.openedx.authentication.')}
for filter_type, pipeline in found.items():
    print(filter_type, '->', pipeline)
if len(found) != 6:
    raise SystemExit('EXPECTED 6 authentication filter mappings, found %d' % len(found))
"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

set +x
cat <<EOF

=============================================================================
ENT-11568 integration test fixtures provisioned.
=============================================================================

Enterprises:
  "${GRYFFINDOR_ENTERPRISE_NAME}"  (slug=${GRYFFINDOR_REALM}; uuid=${GRYFFINDOR_UUID:-<lookup-failed>})
  "${SLYTHERIN_ENTERPRISE_NAME}"   (slug=${SLYTHERIN_REALM})

Keycloak SSO users (password "testpass"):
  ${GRYFFINDOR_LEARNER_USERNAME}    -> has LMS account   -> LOGIN flow
  ${SLYTHERIN_LEARNER_USERNAME}     -> has LMS account   -> LOGIN flow
  ${GRYFFINDOR_NEWCOMER_USERNAME}   -> no LMS account    -> REGISTRATION flow
  ${SLYTHERIN_NEWCOMER_USERNAME}    -> no LMS account    -> REGISTRATION flow

LMS learner users (password "edx"):
  ${GRYFFINDOR_LEARNER_EMAIL}   -> ${GRYFFINDOR_ENTERPRISE_NAME} only
  ${SLYTHERIN_LEARNER_EMAIL}    -> ${SLYTHERIN_ENTERPRISE_NAME} only
  ${DUAL_LEARNER}@example.com   -> BOTH enterprises

-----------------------------------------------------------------------------
Prerequisites
-----------------------------------------------------------------------------

  1. In devstack/configuration_files/lms.yml, then restart the LMS:
       ENABLE_ENTERPRISE_INTEGRATION: true
       FEATURES:
         ENABLE_AUTHN_MICROFRONTEND: true

  2. In /etc/hosts on the machine running the browser:
       127.0.0.1 edx.devstack.keycloak

-----------------------------------------------------------------------------
LogistrationViewEnterpriseContextEnricher  (legacy page context)
-----------------------------------------------------------------------------

  1. a. Logged out, open:
        ${LMS_BASE}/login?tpa_hint=saml-${GRYFFINDOR_REALM}&skip_authn_mfe=1
     Expect: stay on ${LMS_BASE}/login?tpa_hint=saml-${GRYFFINDOR_REALM}&skip_authn_mfe=1
       with the enterprise sidebar showing the Gryffindor logo and a welcome
       message naming Gryffindor.
     b. The other two context values this step sets are request-independent and
        have no visible effect, so check them once from the CLI:
        curl -s '${LMS_BASE}/login?skip_authn_mfe=1' | grep -oE '"(is_enterprise_enable|enterprise_slug_login_url)": [^,]*'
     Expect: exactly these two lines:
       "enterprise_slug_login_url": "/enterprise/login"
       "is_enterprise_enable": true

  2. a. Logged out, open:  ${LMS_BASE}/login?skip_authn_mfe=1
     Expect: stay on ${LMS_BASE}/login?skip_authn_mfe=1 with no enterprise
       sidebar — just the standard login panel.

-----------------------------------------------------------------------------
LogistrationViewEnterpriseCookieSetter  (legacy page response cookies)
-----------------------------------------------------------------------------

  3. a. With devtools open (Application > Cookies > ${LMS_BASE}), load:
        ${LMS_BASE}/login?tpa_hint=saml-${GRYFFINDOR_REALM}&skip_authn_mfe=1
     Expect: stay on that URL; experiments_is_enterprise == true, and the
       enterprise_customer_uuid cookie deleted (Set-Cookie with an empty value /
       past expiry).

  4. a. With devtools open, load:  ${LMS_BASE}/login?skip_authn_mfe=1
     Expect: stay on that URL; experiments_is_enterprise == false.

-----------------------------------------------------------------------------
AuthnMFEEnterpriseContextEnricher  (authn MFE context API)
-----------------------------------------------------------------------------

  5. a. curl -s '${LMS_BASE}/api/mfe_context?next=%2Fdashboard&tpa_hint=saml-${GRYFFINDOR_REALM}' | jq .contextData.enterpriseBranding
     Expect: enterpriseName "Gryffindor", enterpriseSlug "${GRYFFINDOR_REALM}",
       non-empty enterpriseLogoUrl / enterpriseBrandedWelcomeString /
       platformWelcomeString.

  6. a. curl -s '${LMS_BASE}/api/mfe_context?next=%2Fdashboard' | jq .contextData.enterpriseBranding
     Expect: null.

-----------------------------------------------------------------------------
RegistrationFormEnterpriseOverrides  (legacy registration form)
-----------------------------------------------------------------------------

  7. skip_registration_form=True (devstack default) hides each field the SSO
     provider supplied. Devstack asserts only email + first/last name, so only
     Public Username and Email get hidden.
     a. Reset:  make dev.provision.keycloak
     b. Logged out:  ${LMS_BASE}/auth/login/tpa-saml/?auth_entry=register&idp=${GRYFFINDOR_REALM}
     c. Authenticate at Keycloak as ${GRYFFINDOR_NEWCOMER_USERNAME}.
     Expect: land on ${LMS_BASE}/register with Public Username and Email hidden;
       Full Name and Country/Region visible, editable, empty; Terms of Service +
       create button remain.

  8. skip_registration_form=False hides nothing.
     a. In admin, add a provider version with skip_registration_form=False.
     b. Logged out:  ${LMS_BASE}/auth/login/tpa-saml/?auth_entry=register&idp=${GRYFFINDOR_REALM}
     c. Authenticate at Keycloak as ${GRYFFINDOR_NEWCOMER_USERNAME}.
     Expect: land on ${LMS_BASE}/register with every field VISIBLE. Platform TPA
       prefill fills Public Username (read-only) and Email (editable); Full Name
       and Country/Region empty and editable.
     Cleanup:  make dev.provision.keycloak

-----------------------------------------------------------------------------
LoginFormEnterpriseOverrides  (legacy login form)
-----------------------------------------------------------------------------

  9. The login form only renders when the asserted email has an LMS account but
     NO social-auth link and NO ECU for the IdP, and provisioning does not clear
     a social-auth link from a prior login, so delete both explicitly.
     a. Reset:  make dev.provision.keycloak
     b. Delete the learner's social-auth link + enterprise membership (keeps the account):
        docker exec -i edx.devstack.lms python manage.py lms --settings devstack shell -c "from django.contrib.auth import get_user_model; from enterprise.models import EnterpriseCustomerUser; from social_django.models import UserSocialAuth; uid = get_user_model().objects.get(username='${GRYFFINDOR_LEARNER_USERNAME}').id; print(UserSocialAuth.objects.filter(user_id=uid).delete()); print(EnterpriseCustomerUser.objects.filter(user_id=uid).delete())"
     c. Logged out:  ${LMS_BASE}/auth/login/tpa-saml/?auth_entry=login&idp=${GRYFFINDOR_REALM}
     d. Authenticate at Keycloak as ${GRYFFINDOR_LEARNER_USERNAME}.
     Expect: land on ${LMS_BASE}/login with Email pre-filled
       ${GRYFFINDOR_LEARNER_EMAIL} and read-only. Do NOT submit (it would re-link).
     Cleanup:  make dev.provision.keycloak

-----------------------------------------------------------------------------
Authn MFE redirect matrix  (login_form.py, no enterprise term left)
-----------------------------------------------------------------------------

 10. [B2C -> MFE]
     a. Logged out, open:  ${LMS_BASE}/login
     Expect: land on ${AUTHN_MFE_BASE}/login.

 11. [B2B non-SAML -> MFE]
     a. Logged out, open:
        ${LMS_BASE}/login?enterprise_customer=${GRYFFINDOR_UUID:-<gryffindor-uuid>}
     Expect: land on
        ${AUTHN_MFE_BASE}/login?enterprise_customer=${GRYFFINDOR_UUID:-<gryffindor-uuid>}
       and NOT ${LMS_BASE}/login.

 12. [SAML pipeline -> legacy]
     a. Reset:  make dev.provision.keycloak
     b. Logged out:  ${LMS_BASE}/auth/login/tpa-saml/?auth_entry=login&idp=${GRYFFINDOR_REALM}
     c. Authenticate at Keycloak as ${GRYFFINDOR_NEWCOMER_USERNAME}.
     Expect: land on ${LMS_BASE}/register (send_to_registration_first=True is the
       devstack default) with Gryffindor branding, and never on ${AUTHN_MFE_BASE}.

-----------------------------------------------------------------------------
PostLoginEnterpriseRedirect  (login_user; only runs with the authn MFE enabled)
-----------------------------------------------------------------------------

 13. a. Open ${AUTHN_MFE_BASE}/login and sign in as
        ${DUAL_LEARNER}@example.com / edx
     Expect: land on ${LMS_BASE}/enterprise/select/active/?success_url=%2Fdashboard
       and NOT ${LMS_BASE}/dashboard.

 14. a. Open ${AUTHN_MFE_BASE}/login and sign in as
        ${GRYFFINDOR_LEARNER_EMAIL} / edx
     Expect: land on ${LMS_BASE}/dashboard, with no stop at
       ${LMS_BASE}/enterprise/select/active/.

-----------------------------------------------------------------------------
Regression: TPA form dispatch (platform behavior, unchanged by this ticket)
-----------------------------------------------------------------------------

 15. send_to_registration_first=True sends a brand-new SSO user arriving via
     auth_entry=login to registration. The guard is
     \`skip_email_verification OR send_to_registration_first\`, so hold
     skip_email_verification=False to isolate it.
     a. Reset:  make dev.provision.keycloak
     b. In admin, add a version with skip_email_verification=False,
        send_to_registration_first=True.
     c. Logged out:  ${LMS_BASE}/auth/login/tpa-saml/?auth_entry=login&idp=${GRYFFINDOR_REALM}
     d. Authenticate at Keycloak as ${GRYFFINDOR_NEWCOMER_USERNAME}.
     Expect: land on ${LMS_BASE}/register.
     Cleanup:  make dev.provision.keycloak

 16. send_to_registration_first=False keeps the same newcomer on login.
     a. In admin, add a version with skip_email_verification=False,
        send_to_registration_first=False.
     b. Logged out:  ${LMS_BASE}/auth/login/tpa-saml/?auth_entry=login&idp=${GRYFFINDOR_REALM}
     c. Authenticate at Keycloak as ${GRYFFINDOR_NEWCOMER_USERNAME}.
     Expect: land on ${LMS_BASE}/login.
     Cleanup:  make dev.provision.keycloak

EOF

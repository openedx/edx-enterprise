#!/usr/bin/env bash
#
# Provision a devstack environment for integration-testing the six new
# openedx-filter pipeline steps added in ticket ENT-11568
# (Logistration Enterprise Context).
#
# Instructions:
#
# 1. Start relevant devstack services:
#
#     make dev.up.lms+frontend-app-authn+frontend-app-learner-portal-enterprise
#
# 2. From the edx-enterprise directory, provision keycloak and run this script:
#
#     make dev.provision.keycloak
#     ./scripts/provision-integration-test-ENT-11568.sh

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

# Username for a learner linked to BOTH enterprises (Gryffindor + Slytherin)
# to trigger a multi-enterprise drop-down selection interstitial during login.
DUAL_LEARNER="dual_enterprise_learner"

LMS_BASE="http://localhost:18000"

# ---------------------------------------------------------------------------
# Helpers -- run a Django management command inside the LMS container
# ---------------------------------------------------------------------------

lms_manage() {
    docker exec -i edx.devstack.lms python manage.py lms --settings devstack "$@"
}

# ---------------------------------------------------------------------------
# Step 1: Create a learner linked to two enterprises
# ---------------------------------------------------------------------------
# Create an enterprise learner linked with both enterprises.
# The first --enterprise-name occurrence is made into the "active" enterprise.
lms_manage create_enterprise_linked_learner \
    --username "$DUAL_LEARNER" \
    --enterprise-name "$GRYFFINDOR_ENTERPRISE_NAME" \
    --enterprise-name "$SLYTHERIN_ENTERPRISE_NAME"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

set +x
cat <<EOF

=============================================================================
ENT-11568 integration test fixtures provisioned.
=============================================================================

Enterprises:
  "${GRYFFINDOR_ENTERPRISE_NAME}"  (slug=${GRYFFINDOR_REALM}; primary tenant)
  "${SLYTHERIN_ENTERPRISE_NAME}"   (slug=${SLYTHERIN_REALM};  secondary tenant)

Keycloak SSO users (username / password):
  ${GRYFFINDOR_LEARNER_USERNAME} / testpass    -> matching LMS account -> LOGIN flow
  ${SLYTHERIN_LEARNER_USERNAME} / testpass     -> matching LMS account -> LOGIN flow
  ${GRYFFINDOR_NEWCOMER_USERNAME} / testpass   -> no LMS account       -> REGISTRATION flow
  ${SLYTHERIN_NEWCOMER_USERNAME} / testpass    -> no LMS account       -> REGISTRATION flow

LMS Learner users (email / password):
  ${GRYFFINDOR_LEARNER_EMAIL} / edx    -> linked to ${GRYFFINDOR_ENTERPRISE_NAME} only
  ${SLYTHERIN_LEARNER_EMAIL} / edx     -> linked to ${SLYTHERIN_ENTERPRISE_NAME} only
  ${DUAL_LEARNER}@example.com / edx    -> linked to BOTH enterprises

-----------------------------------------------------------------------------
Toggles used below
-----------------------------------------------------------------------------

* Authn MFE:   ENABLE_AUTHN_MICROFRONTEND in your devstack's
               py_configuration_files/lms.py.  Changing it requires an LMS
               restart:  docker restart edx.devstack.lms
* Provider:    SAMLProviderConfig fields (skip_registration_form,
               send_to_registration_first) via Django admin at
               ${LMS_BASE}/admin/third_party_auth/samlproviderconfig/ .
               It is a versioned ConfigurationModel: "add" clones the current
               values into a new active version; no restart needed.
               NOTE: re-running \`make dev.provision.keycloak\` recreates the
               provider with the provisioned defaults, reverting any admin
               toggle (skip_registration_form=True, send_to_registration_first=True).

The enterprise logistration overrides live in the LEGACY logistration code
path.  The legacy page renders when the Authn MFE is OFF (everyone) OR when the
MFE is ON and the request is in an enterprise context (the veto in Part B keeps
enterprise users on the legacy page).

=============================================================================
PART A -- Authn MFE OFF   (set ENABLE_AUTHN_MICROFRONTEND=False, restart LMS)
=============================================================================

  1. Test LogistrationContextEnricher (via LogistrationContextRequested).
     Injects enterprise branding into the logistration page context.
     a. In a fresh/incognito session (logged out), open:
        ${LMS_BASE}/login?tpa_hint=saml-${GRYFFINDOR_REALM}
     Expected: the login page shows an enterprise welcome panel (sidebar)
        branded for Gryffindor -- you should see the name "Gryffindor" and the
        Gryffindor crest logo (the branding set by provisioning), with the
        scarlet/gold house colors.  To confirm the raw data, view page source:
        the embedded context has "enable_enterprise_sidebar": true and
        "enterprise_name": "Gryffindor".

  2. [control] Without enterprise context, LogistrationContextEnricher does nothing.
     a. In a fresh/incognito session (logged out), open the plain login page:
        ${LMS_BASE}/login   (no tpa_hint)
     Expected: the standard login page renders with NO enterprise welcome panel
        and no enterprise name/logo anywhere.  Page source shows
        "enable_enterprise_sidebar": false.

  3. Test LogistrationCookieSetter (via LogistrationResponseRendered).
     Sets the experiments_is_enterprise cookie from enable_enterprise_sidebar.
     a. Open devtools (Application > Cookies > ${LMS_BASE}), then load:
        ${LMS_BASE}/login?tpa_hint=saml-${GRYFFINDOR_REALM}
     Expected: the experiments_is_enterprise cookie exists with value exactly
        true (JSON).  Optional secondary check: in the Network tab, the /login
        response's Set-Cookie headers clear the enterprise_customer_uuid cookie
        (an expired Set-Cookie), preventing a stale enterprise context from
        persisting.

  4. [control] Without enterprise context, the cookie value is false.
     a. Open devtools (Application > Cookies > ${LMS_BASE}), then load the plain
        login page:  ${LMS_BASE}/login   (no tpa_hint)
     Expected: the experiments_is_enterprise cookie value is exactly false (JSON).

  5. Test RegistrationFormEnterpriseOverrides (via RegistrationFormTPAOverridesRequested).
     With skip_registration_form=True in an enterprise context, the SSO-prefilled
     fields are hidden so only Terms of Service remains.  (Provisioned defaults:
     skip_registration_form=True, send_to_registration_first=True,
     sync_learner_profile_data=False, so the hiding is attributable to the
     enterprise step, not the platform's own path.)
     a. Reset to a clean slate:  make dev.provision.keycloak
     b. Logged out, start SSO registration:
        ${LMS_BASE}/auth/login/tpa-saml/?auth_entry=register&idp=${GRYFFINDOR_REALM}
     c. Authenticate at Keycloak as ${GRYFFINDOR_NEWCOMER_USERNAME} (password "testpass").
     Expected: the registration form shows no editable inputs for full name,
        public username, or email (they are hidden/pre-filled); effectively only
        the Terms of Service agreement and the account-creation button remain.

  6. [control] With skip_registration_form=False, the fields are not hidden.
     a. In Django admin (${LMS_BASE}/admin/third_party_auth/samlproviderconfig/),
        add a new provider version with skip_registration_form=False (no restart).
     b. Logged out, start SSO registration again:
        ${LMS_BASE}/auth/login/tpa-saml/?auth_entry=register&idp=${GRYFFINDOR_REALM}
     c. Authenticate at Keycloak as ${GRYFFINDOR_NEWCOMER_USERNAME} (password "testpass").
     Expected: the full registration form renders with the full name, username,
        and email fields VISIBLE (pre-filled from SSO but editable).
     Cleanup: make dev.provision.keycloak  (restores skip_registration_form=True).

  7. Test LoginFormEnterpriseOverrides (via LoginFormTPAOverridesRequested).
     For an enterprise SSO user landing on the login form, the email field is
     pre-filled and made read-only.  The login form only renders mid-pipeline
     when the user is NOT sent to registration first, so toggle that off.
     a. In Django admin (${LMS_BASE}/admin/third_party_auth/samlproviderconfig/),
        add a new provider version with send_to_registration_first=False.
     b. Logged out, start SSO login:
        ${LMS_BASE}/auth/login/tpa-saml/?auth_entry=login&idp=${GRYFFINDOR_REALM}
     c. Authenticate at Keycloak as ${GRYFFINDOR_NEWCOMER_USERNAME} (password "testpass").
     Expected: the login form's Email field is pre-filled with
        ${GRYFFINDOR_NEWCOMER_USERNAME}@example.com and is read-only (greyed out; you cannot edit it).
     Cleanup: make dev.provision.keycloak  (restores send_to_registration_first=True).
     NOTE: this test is the least settled -- the exact conditions under which the
     enterprise login-form override renders depend on the SSO/association path.
     Confirm in-browser and adjust these steps as needed.

=============================================================================
PART B -- Authn MFE ON    (set ENABLE_AUTHN_MICROFRONTEND=True, restart LMS)
=============================================================================

  8. Test EnterpriseMFERedirectVeto (via LogistrationMFERedirectRequested).
     In an enterprise context the authn-MFE redirect is vetoed, so the legacy
     branded page renders instead.
     a. Logged out, open the enterprise-context login:
        ${LMS_BASE}/login?tpa_hint=saml-${GRYFFINDOR_REALM}
     Expected: the browser STAYS on ${LMS_BASE}/login (the address bar host does
        not change) and renders the legacy Gryffindor-branded page (the same
        welcome panel/crest as test 1).  It is NOT redirected to the authn MFE.
     (With the MFE on, tests 1 and 3 also fire here, since the veto renders the
     legacy page.)

  9. [control] Without enterprise context, the request is redirected to the MFE.
     a. Logged out, open the plain login page:  ${LMS_BASE}/login   (no tpa_hint)
     Expected: the browser is redirected away from ${LMS_BASE}/login to the authn
        micro-frontend (the app at AUTHN_MICROFRONTEND_URL, a different host/port
        than ${LMS_BASE}).

=============================================================================
PART C -- post-login redirect   (independent of the Authn MFE toggle)
=============================================================================

  10. Test PostLoginEnterpriseRedirect (via PostLoginRedirectURLRequested).
      A learner belonging to more than one enterprise is redirected to the
      enterprise-selection page after login.
      a. Log in with email/password as  ${DUAL_LEARNER}@example.com / edx
      Expected: after login the browser lands on the enterprise selection page --
         the address bar shows /enterprise/select/active/?success_url=... -- and
         the page prompts you to choose between Gryffindor and Slytherin instead
         of loading the dashboard.

  11. [control] A single-enterprise learner is not redirected to the selection page.
      a. Log in with email/password as  ${GRYFFINDOR_LEARNER_USERNAME}@example.com / edx
         (the baseline's Gryffindor SSO learner, linked to Gryffindor only; use its
         LMS password "edx" here, not its Keycloak password "testpass").
      Expected: no selection page; the learner proceeds straight to the normal
         post-login destination (the ${LMS_BASE}/dashboard learner dashboard).

EOF

"""
Provision SAML / TPA records in the LMS for Keycloak IdP testing.

Run inside the LMS container via:
    manage.py lms shell < provision-tpa.py

SHARED configuration -- the one Keycloak service and the single LMS service
provider -- is read from environment variables (see keycloak-devstack.env).

PER-TENANT configuration lives in the TENANTS list below.  A "tenant" is one
Keycloak realm plus one Open edX enterprise customer, both sharing the same
Keycloak service and the same LMS.  For each tenant the realm name, the
SAMLProviderConfig slug, the provider_id (``saml-<name>``), and the enterprise
slug are all the SAME arbitrary token (e.g. "gryffindor"), so one memorable name
identifies everything about the tenant.  The Keycloak side of each tenant (its
realm and SSO users) is defined in keycloak-realms/<name>.json; the per-tenant
user emails below MUST match that file.
"""
import os
import sys

from django.contrib.sites.models import Site
from django.core.management import call_command

import enterprise
from common.djangoapps.third_party_auth.models import (
    SAMLConfiguration,
    SAMLProviderConfig,
    SAMLProviderData,
)
from enterprise.constants import ENTERPRISE_LEARNER_ROLE
from enterprise.devstack_api import (
    delete_user_and_enterprise_links,
    get_or_create_enterprise_branding,
    get_or_create_enterprise_identity_provider,
    get_or_create_enterprise_user,
    link_user_to_enterprise,
    seed_global_users,
)
from enterprise.models import EnterpriseCustomer

# ---------------------------------------------------------------------------
# Shared configuration (one Keycloak service, one LMS service provider)
# ---------------------------------------------------------------------------
KEYCLOAK_URL = os.environ['KEYCLOAK_URL']
SP_ENTITY_ID = os.environ['SP_ENTITY_ID']
OID_EMAIL = os.environ['OID_EMAIL']
OID_GIVEN_NAME = os.environ['OID_GIVEN_NAME']
OID_SURNAME = os.environ['OID_SURNAME']

# Keycloak-side password entered at the IdP (matches keycloak-realms/*.json).
SSO_PASSWORD = 'testpass'

# provision-tpa/ ships alongside the enterprise package (in devstack's editable
# install, /edx/src/edx-enterprise/provision-tpa).  Derive it from the package
# location rather than hard-coding the mount path.
LOGO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(enterprise.__file__))),
    'provision-tpa',
)

# ---------------------------------------------------------------------------
# Per-tenant configuration
# ---------------------------------------------------------------------------
# Each "tenant" represents an fictional organization with their own (keycloak-backed) IdP
# and associated enterprise within the database.
TENANTS = [
    {
        'name': os.environ['GRYFFINDOR_REALM'],
        'enterprise_name': os.environ['GRYFFINDOR_ENTERPRISE_NAME'],
        'primary_color': os.environ['GRYFFINDOR_PRIMARY_COLOR'],
        'secondary_color': os.environ['GRYFFINDOR_SECONDARY_COLOR'],
        'tertiary_color': os.environ['GRYFFINDOR_TERTIARY_COLOR'],
        'learner_username': os.environ['GRYFFINDOR_LEARNER_USERNAME'],
        'learner_email': os.environ['GRYFFINDOR_LEARNER_EMAIL'],
        'learner_first_name': os.environ['GRYFFINDOR_LEARNER_FIRST_NAME'],
        'learner_last_name': os.environ['GRYFFINDOR_LEARNER_LAST_NAME'],
        'newcomer_username': os.environ['GRYFFINDOR_NEWCOMER_USERNAME'],
        'newcomer_email': os.environ['GRYFFINDOR_NEWCOMER_EMAIL'],
    },
    {
        'name': os.environ['SLYTHERIN_REALM'],
        'enterprise_name': os.environ['SLYTHERIN_ENTERPRISE_NAME'],
        'primary_color': os.environ['SLYTHERIN_PRIMARY_COLOR'],
        'secondary_color': os.environ['SLYTHERIN_SECONDARY_COLOR'],
        'tertiary_color': os.environ['SLYTHERIN_TERTIARY_COLOR'],
        'learner_username': os.environ['SLYTHERIN_LEARNER_USERNAME'],
        'learner_email': os.environ['SLYTHERIN_LEARNER_EMAIL'],
        'learner_first_name': os.environ['SLYTHERIN_LEARNER_FIRST_NAME'],
        'learner_last_name': os.environ['SLYTHERIN_LEARNER_LAST_NAME'],
        'newcomer_username': os.environ['SLYTHERIN_NEWCOMER_USERNAME'],
        'newcomer_email': os.environ['SLYTHERIN_NEWCOMER_EMAIL'],
    },
]

site = Site.objects.get_current()

# ---------------------------------------------------------------------------
# Step 1: Create the shared SAMLConfiguration (service-provider config)
# ---------------------------------------------------------------------------
# This simply enables SAML for this LMS installation.
print('\n--- Step 1: Create shared SAMLConfiguration ---')
saml_config = SAMLConfiguration(
    site=site,
    slug='default',
    enabled=True,
    entity_id=SP_ENTITY_ID,
)
saml_config.save()
print(f'Created SAMLConfiguration version (slug=default, entity_id={SP_ENTITY_ID})')

# ---------------------------------------------------------------------------
# Step 2: Seed the globally-scoped enterprise users (once, not per tenant)
# ---------------------------------------------------------------------------
# The operator, worker, and super-admin users apply across all enterprises, so
# they are created a single time here and never linked to a specific enterprise.
print('\n--- Step 2: Seed global enterprise users ---')
seed_global_users()

# ---------------------------------------------------------------------------
# Step 3: Provision each tenant (enterprise + IdP + branding + users)
# ---------------------------------------------------------------------------
for tenant in TENANTS:
    name = tenant['name']
    enterprise_name = tenant['enterprise_name']
    idp_display_name = f'{enterprise_name} IdP'
    provider_id = f'saml-{name}'
    idp_entity_id = f'{KEYCLOAK_URL}/realms/{name}'
    idp_metadata_url = f'{idp_entity_id}/protocol/saml/descriptor'
    logo_filename = f'{name}.png'  # provision-tpa/<realm>.png
    print(f'\n=== Tenant "{enterprise_name}" (realm/slug={name}) ===')

    # Step A: Seed the enterprise customer (catalog + groups) without any role
    # users -- the global users are seeded once above, and this tenant's SSO
    # login account is created in Step E.  The enterprise slug is
    # slugify(enterprise_name) == name, matching the realm/provider name.
    print(f'--- Step A: Seed enterprise "{enterprise_name}" ---')
    call_command('seed_enterprise_devstack_data', enterprise_name=enterprise_name, no_create_users=True)
    ec = EnterpriseCustomer.objects.get(slug=name)

    # Step B: Create the tenant's SAMLProviderConfig (its Keycloak IdP).
    print('--- Step B: Create SAMLProviderConfig ---')
    # ConfigurationModel with KEY_FIELDS = ('slug',); each save is a new version.
    provider_config = SAMLProviderConfig(
        site=site,
        slug=name,
        name=idp_display_name,
        entity_id=idp_entity_id,
        metadata_source=idp_metadata_url,
        enabled=True,
        visible=True,
        skip_registration_form=True,
        skip_email_verification=True,
        send_to_registration_first=True,
        attr_user_permanent_id=OID_EMAIL,
        attr_email=OID_EMAIL,
        attr_first_name=OID_GIVEN_NAME,
        attr_last_name=OID_SURNAME,
    )
    provider_config.save()
    print(f'Created SAMLProviderConfig version (slug={name}, entity_id={idp_entity_id})')

    # Step C: Link the IdP to the enterprise so tpa_hint and SSO logins resolve
    # enterprise context.
    print('--- Step C: Link IdP to enterprise ---')
    get_or_create_enterprise_identity_provider(enterprise_customer=ec, provider_id=provider_id)
    print(f'Linked IdP {provider_id} -> {ec.name}')

    # Step D: Set enterprise branding (logo + house colors) so the logistration
    # sidebar renders a visually distinct, verifiable brand per tenant.
    print('--- Step D: Set enterprise branding ---')
    get_or_create_enterprise_branding(
        enterprise_customer=ec,
        logo_path=os.path.join(LOGO_DIR, logo_filename),
        primary_color=tenant['primary_color'],
        secondary_color=tenant['secondary_color'],
        tertiary_color=tenant['tertiary_color'],
    )
    print(f'Branding set (logo={logo_filename}, colors {tenant["primary_color"]}/{tenant["secondary_color"]})')

    # Step E: Create the fully-linked LMS user.
    # get_or_create_enterprise_user makes the account with the tenant's learner
    # email, which equals the Keycloak user's email so enterprise_associate_by_email
    # can match them and sign the user in.  The email and first/last name all come
    # from the same env values the realm JSON uses for the SAML assertion.  It also
    # grants the enterprise_learner role so the user is provisioned identically to
    # seed_enterprise_devstack_data's tenant learners.
    print('--- Step E: Create fully-linked LMS user ---')
    learner = get_or_create_enterprise_user(
        username=tenant['learner_username'],
        role=ENTERPRISE_LEARNER_ROLE,
        enterprise_customer=ec,
        email=tenant['learner_email'],
        first_name=tenant['learner_first_name'],
        last_name=tenant['learner_last_name'],
    )
    link_user_to_enterprise(user=learner, enterprise_customer=ec)
    print(f'Fully-linked account ready: {learner.username} ({learner.email})')

    # Step F: Enforce that the newcomer SSO user has NO LMS user.
    # Registering via SSO in a prior run creates one, so delete it every run to
    # idempotently converge back to "no account" (the newcomer reset).  The email
    # is the tenant's explicit newcomer email -- the same value the realm JSON uses
    # for the SAML assertion -- so this always targets the account SSO would create.
    print('--- Step F: Ensure newcomer has no LMS user ---')
    newcomer_email = tenant['newcomer_email']
    deleted = delete_user_and_enterprise_links(email=newcomer_email)
    if deleted:
        print(f'Deleted {deleted} stale LMS account(s) for {newcomer_email}')
    print(f'Newcomer has no LMS account: {tenant["newcomer_username"]}')

# ---------------------------------------------------------------------------
# Step 4: Fetch SAML metadata for all providers (single pull)
# ---------------------------------------------------------------------------
print('\n--- Step 4: Fetch SAML metadata (saml --pull) ---')
# saml --pull fetches metadata for ALL enabled providers. If any pre-existing
# provider has an unreachable metadata URL, the command will fail.
try:
    call_command('saml', pull=True)
except Exception as exc:
    print(f'\nERROR: saml --pull failed: {exc}')
    print('This usually means a pre-existing SAMLProviderConfig has an unreachable metadata URL.')
    print(f'Audit providers at: {SP_ENTITY_ID}/admin/third_party_auth/samlproviderconfig/?show_history=1')
    sys.exit(1)

# ---------------------------------------------------------------------------
# Step 5: Verify SAMLProviderData for each tenant
# ---------------------------------------------------------------------------
print('\n--- Step 5: Verify SAMLProviderData ---')
for tenant in TENANTS:
    idp_entity_id = f'{KEYCLOAK_URL}/realms/{tenant["name"]}'
    provider_data = SAMLProviderData.objects.filter(entity_id=idp_entity_id)
    if provider_data.exists():
        d = provider_data.latest('fetched_at')
        print(f'{tenant["name"]}: fetched {d.fetched_at}, sso_url={d.sso_url}, public_key={bool(d.public_key)}')
    else:
        print(f'ERROR: No SAMLProviderData for {tenant["name"]} ({idp_entity_id}). Check saml --pull output.')
        sys.exit(1)

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
print('\n=== LMS TPA provisioning complete ===')
for tenant in TENANTS:
    print(f'\n[{tenant["enterprise_name"]}]')
    print(f'  SAML SSO URL: http://localhost:18000/auth/login/tpa-saml/?auth_entry=login&idp={tenant["name"]}')
    print(f'  Fully-linked (has LMS account): Keycloak {tenant["learner_username"]} / {SSO_PASSWORD}')
    print(f'  Newcomer (no LMS account):      Keycloak {tenant["newcomer_username"]} / {SSO_PASSWORD}')

"""
Provision SAML / TPA records in the LMS for Keycloak IdP testing.

Run inside the LMS container via:
    manage.py lms shell < provision-tpa.py

All configuration is read from environment variables (see keycloak-devstack.env).
"""
import os
import sys

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management import call_command

from common.djangoapps.student.models import UserProfile
from common.djangoapps.third_party_auth.models import (
    SAMLConfiguration,
    SAMLProviderConfig,
    SAMLProviderData,
)
from enterprise.models import (
    EnterpriseCustomer,
    EnterpriseCustomerIdentityProvider,
    EnterpriseCustomerUser,
)

User = get_user_model()

# ---------------------------------------------------------------------------
# Read configuration from environment (sourced from keycloak-devstack.env)
# ---------------------------------------------------------------------------
KEYCLOAK_URL = os.environ['KEYCLOAK_URL']
REALM_NAME = os.environ['REALM_NAME']
SP_ENTITY_ID = os.environ['SP_ENTITY_ID']
SAML_SLUG = os.environ['SAML_SLUG']
OID_EMAIL = os.environ['OID_EMAIL']
OID_GIVEN_NAME = os.environ['OID_GIVEN_NAME']
OID_SURNAME = os.environ['OID_SURNAME']
TEST_USERNAME = os.environ['TEST_USERNAME']
TEST_EMAIL = os.environ['TEST_EMAIL']
TEST_PASSWORD = os.environ['TEST_PASSWORD']
TEST_FIRST_NAME = os.environ['TEST_FIRST_NAME']
TEST_LAST_NAME = os.environ['TEST_LAST_NAME']
LMS_USERNAME = os.environ['LMS_USERNAME']
LMS_PASSWORD = os.environ['LMS_PASSWORD']

# Derived constants
IDP_ENTITY_ID = f'{KEYCLOAK_URL}/realms/{REALM_NAME}'
IDP_METADATA_URL = f'{IDP_ENTITY_ID}/protocol/saml/descriptor'
PROVIDER_ID = f'saml-{SAML_SLUG}'

# ---------------------------------------------------------------------------
# Step 1: Seed enterprise devstack data
# ---------------------------------------------------------------------------
print('\n--- Step 1: Seed enterprise devstack data ---')
call_command('seed_enterprise_devstack_data')

# ---------------------------------------------------------------------------
# Step 2: Create SAMLConfiguration (global SP config)
# ---------------------------------------------------------------------------
print('\n--- Step 2: Create SAMLConfiguration ---')
site = Site.objects.get_current()
# SAMLConfiguration is a ConfigurationModel with KEY_FIELDS = ('site_id', 'slug').
# Multiple rows per (site, slug) is expected — each row is a version.
# Just create a new version with the desired settings.
saml_config = SAMLConfiguration(
    site=site,
    slug='default',
    enabled=True,
    entity_id=SP_ENTITY_ID,
)
saml_config.save()
print(f'Created SAMLConfiguration version (slug=default, entity_id={SP_ENTITY_ID})')

# ---------------------------------------------------------------------------
# Step 3: Create SAMLProviderConfig (Keycloak IdP)
# ---------------------------------------------------------------------------
print('\n--- Step 3: Create SAMLProviderConfig ---')
# SAMLProviderConfig is a ConfigurationModel with KEY_FIELDS = ('slug',).
# Multiple rows per slug is expected — each row is a version.
provider_config = SAMLProviderConfig(
    site=site,
    slug=SAML_SLUG,
    name='Keycloak Devstack IdP',
    entity_id=IDP_ENTITY_ID,
    metadata_source=IDP_METADATA_URL,
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
print(f'Created SAMLProviderConfig version (slug={SAML_SLUG}, entity_id={IDP_ENTITY_ID})')

# ---------------------------------------------------------------------------
# Step 4: Create EnterpriseCustomerIdentityProvider
# ---------------------------------------------------------------------------
print('\n--- Step 4: Create EnterpriseCustomerIdentityProvider ---')
ec = EnterpriseCustomer.objects.get(slug='test-enterprise')
ecidp, created = EnterpriseCustomerIdentityProvider.objects.get_or_create(
    provider_id=PROVIDER_ID,
    enterprise_customer=ec,
)
action = 'Created' if created else 'Already exists'
print(f'{action}: provider_id={PROVIDER_ID}, enterprise={ec.name}')

# ---------------------------------------------------------------------------
# Step 5: Fetch SAML metadata from Keycloak
# ---------------------------------------------------------------------------
print('\n--- Step 5: Fetch SAML metadata (saml --pull) ---')
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
# Step 6: Verify SAMLProviderData
# ---------------------------------------------------------------------------
print('\n--- Step 6: Verify SAMLProviderData ---')
provider_data = SAMLProviderData.objects.filter(entity_id=IDP_ENTITY_ID)
if provider_data.exists():
    d = provider_data.latest('fetched_at')
    print(f'SAMLProviderData fetched at {d.fetched_at}')
    print(f'SSO URL: {d.sso_url}')
    print(f'Public key present: {bool(d.public_key)}')
else:
    print('ERROR: No SAMLProviderData found. Check saml --pull output above.')
    sys.exit(1)

# ---------------------------------------------------------------------------
# Step 7: Verify pipeline injection
# ---------------------------------------------------------------------------
print('\n--- Step 7: Verify pipeline injection ---')
pipeline = settings.SOCIAL_AUTH_PIPELINE
email_step = 'enterprise.tpa_pipeline.enterprise_associate_by_email'
logistration_step = 'enterprise.tpa_pipeline.handle_enterprise_logistration'
missing = []
if email_step not in pipeline:
    missing.append(email_step)
if logistration_step not in pipeline:
    missing.append(logistration_step)
if missing:
    print(f'ERROR: Missing pipeline steps: {missing}')
    sys.exit(1)
print('Pipeline injection verified (enterprise_associate_by_email, handle_enterprise_logistration)')

# ---------------------------------------------------------------------------
# Step 8: Create pre-linked enterprise learner
# ---------------------------------------------------------------------------
print('\n--- Step 8: Create pre-linked enterprise learner ---')
learner, created = User.objects.get_or_create(
    username=LMS_USERNAME,
    defaults={
        'email': TEST_EMAIL,
        'is_active': True,
    },
)
if created:
    learner.set_password(LMS_PASSWORD)
    learner.save()
    print(f'Created LMS user: {learner.username} (email={learner.email})')
else:
    print(f'LMS user already exists: {learner.username}')

UserProfile.objects.get_or_create(
    user=learner,
    defaults={'name': f'{TEST_FIRST_NAME} {TEST_LAST_NAME}'},
)
print('UserProfile ensured')

ecu, created = EnterpriseCustomerUser.objects.get_or_create(
    enterprise_customer=ec,
    user_id=learner.id,
    defaults={'active': True},
)
action = 'Created' if created else 'Already exists'
print(f'EnterpriseCustomerUser {action}: active={ecu.active}')

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
print('\n=== LMS TPA provisioning complete ===')
print(f'SAML login URL: http://localhost:18000/auth/login/tpa-saml/?auth_entry=login&idp={SAML_SLUG}')
print(f'Keycloak login: {TEST_USERNAME} / {TEST_PASSWORD}')

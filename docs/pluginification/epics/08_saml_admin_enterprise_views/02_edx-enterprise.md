# [edx-enterprise] Add SAML provider admin viewsets

Blocked by: [openedx-platform] Remove SAML provider admin views

Add `SAMLProviderConfigViewSet` and `SAMLProviderDataViewSet` to edx-enterprise under the enterprise admin API, restoring the same REST endpoints previously served by openedx-platform. The viewsets import TPA models from `common.djangoapps.third_party_auth` (a deferred import, allowed because these views run inside the LMS process) and enterprise models from `enterprise.models`. Register the new views under the enterprise URL namespace at `enterprise/api/v1/saml/` so the same API contract is preserved.

## A/C

- `enterprise/api/v1/views/saml_provider_config.py` contains `SAMLProviderConfigViewSet` with all CRUD operations matching the original openedx-platform implementation.
- `enterprise/api/v1/views/saml_provider_data.py` contains `SAMLProviderDataViewSet` with all CRUD and `sync_provider_data` action matching the original implementation.
- Both viewsets are wired into `enterprise/api/v1/urls.py` at `auth/saml/v0/`.
- Unit tests cover the CRUD operations and permission checks.

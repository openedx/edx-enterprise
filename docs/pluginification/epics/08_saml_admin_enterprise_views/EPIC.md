# Epic: SAML Admin Enterprise Views

JIRA: ENT-11567

## Purpose

`SAMLProviderConfigViewSet` and `SAMLProviderDataViewSet` in `common/djangoapps/third_party_auth/` import `enterprise.models` directly and exist solely to serve enterprise SAML admin functionality; they have no non-enterprise use case.

## Approach

Move both viewsets into edx-enterprise as admin API views, exposing the same REST API endpoints under the enterprise URL namespace. Remove the original files and their URL registrations from `common/djangoapps/third_party_auth/urls.py` in openedx-platform.

## Blocking Epics

None.

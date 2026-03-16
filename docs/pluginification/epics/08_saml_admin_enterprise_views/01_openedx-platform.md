# [openedx-platform] Remove SAML provider admin views

No tickets block this one.

Remove `SAMLProviderConfigViewSet` from `samlproviderconfig/views.py` and `SAMLProviderDataViewSet` from `samlproviderdata/views.py` in `common/djangoapps/third_party_auth/`. Both viewsets import `enterprise.models` and exist only to serve enterprise admin functionality. Remove the corresponding URL registrations from `common/djangoapps/third_party_auth/urls.py`. The equivalent views will be hosted within edx-enterprise instead.

## A/C

- `SAMLProviderConfigViewSet` and its file `samlproviderconfig/views.py` are deleted from `common/djangoapps/third_party_auth/`.
- `SAMLProviderDataViewSet` and its file `samlproviderdata/views.py` are deleted from `common/djangoapps/third_party_auth/`.
- The two `path('auth/saml/v0/', include('...samlproviderconfig.urls'))` and `path('auth/saml/v0/', include('...samlproviderdata.urls'))` entries are removed from `common/djangoapps/third_party_auth/urls.py`.
- No import of `enterprise` or `enterprise_support` remains in any changed file.
- Existing tests for these viewsets are deleted from openedx-platform.

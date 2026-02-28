# [openedx-filters] Add AccountSettingsReadOnlyFieldsRequested filter

No tickets block this one.

Add a new `AccountSettingsReadOnlyFieldsRequested` filter class to `openedx_filters/learning/filters.py`. This filter is invoked when the account settings API validates which fields may be updated, and allows pipeline steps to remove fields from the editable set (i.e. mark them as read-only). The filter accepts the current set of editable field names and the Django User object, and returns the (possibly reduced) set. No exception class is required. This filter must not be confused with the existing `AccountSettingsRenderStarted` filter, which targets the legacy account settings page render and is not invoked from the account settings API.

## A/C

- A new `AccountSettingsReadOnlyFieldsRequested` class is added to `openedx_filters/learning/filters.py`, inheriting from `OpenEdxPublicFilter`.
- The filter type is `"org.openedx.learning.account.settings.read_only_fields.requested.v1"`.
- `run_filter(cls, editable_fields, user)` accepts a `set` of field name strings and a Django User object, and returns the possibly-reduced set of editable fields.
- No exception subclass is defined on this filter.
- A unit test confirms the filter returns `editable_fields` unchanged when no pipeline steps are configured.

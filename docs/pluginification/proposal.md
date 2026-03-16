# Enterprise Plugin Migration: Proposed Epics

## Instructions for Second-Pass AI

Read CLAUDE.md in full before generating any tickets or diffs. This proposal lists all proposed
epics with exact filenames and function names for the enterprise logic to be migrated. Each epic
corresponds to one directory under `epics/`. For each epic, produce:

1. `EPIC.md` — purpose (1-2 sentences) + selected approach (1-3 sentences)
2. One or more story ticket `.md` files per repo affected (`01_openedx-platform.md`,
   `02_openedx-filters.md`, `03_edx-enterprise.md`, etc.)
3. A sibling `.diff` for each `.md` ticket — a complete, compilable implementation diff

Story tickets must follow the format in CLAUDE.md: ticket name as H1 header (prefixed with
`[<repo-name>] `), any blocking ticket, one-paragraph description, and A/C section.

Diffs should include test file changes (modify existing tests to not import enterprise/consent
directly, or update them to mock the new filter/signal interface). Diffs must be complete —
do not produce placeholder or stub diffs.

### Important constraints from CLAUDE.md:

- Do NOT use "Enterprise" in filter class names, filter types, or filter exceptions, and avoid
  mentioning enterprise in openedx-filters docstrings/comments.
- All enterprise/consent imports must be removed from openedx-platform — no try/except
  compatibility shims.
- Enterprise_support functions used by multiple epics can be kept in enterprise_support
  temporarily and called by edx-enterprise plugin steps until they are fully replaced.

### Repos and key reference files:

- `openedx-platform/` — platform to be decoupled
- `openedx-filters/` — where new filter class definitions live
  (`openedx_filters/learning/filters.py`)
- `edx-enterprise/` — where new PipelineStep and signal handler implementations live
- `edx-django-utils/edx_django_utils/plugins/plugin_settings.py` — for settings epic
- Existing filter config pattern: `openedx-platform/lms/envs/production.py` lines 73-87
  (exclusion list) and lines 271-277 (TRACKING_BACKENDS merge logic)
- Retirement signals: `openedx-platform/openedx/core/djangoapps/user_api/accounts/signals.py`

---

## Proposed Epics

---

### 01_grades_analytics_event_enrichment

**Current location:**
- `openedx-platform/lms/djangoapps/grades/events.py`
  - `get_grade_data_event_context()` — line 30 imports
    `from openedx.features.enterprise_support.context import get_enterprise_event_context`
  - Lines ~169-170: `context.update(get_enterprise_event_context(user_id, course_id))`
- `openedx-platform/openedx/features/enterprise_support/context.py`
  - `get_enterprise_event_context(user_id, course_id)` — returns
    `{'enterprise_uuid': '<uuid>'}` or `{}` for non-enterprise learners

**Migration approach:** New openedx-filter (data must flow back to the caller).

**New filter:** `GradeEventContextRequested` in `openedx_filters/learning/filters.py`
- Signature: `run_filter(context, user_id, course_id)` → returns updated context dict
- Filter type string: `"org.openedx.learning.grade.context.requested.v1"`
- No exception class needed (fail_silently=True)
- Add to `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py`

**edx-enterprise step:** `GradeEventContextEnricher(PipelineStep)` in edx-enterprise
- Queries `EnterpriseCustomerUser` to look up enterprise UUID for user_id
- Returns `{"context": {**context, "enterprise_uuid": str(uuid)}}`

**Repos touched:** openedx-filters (new filter), openedx-platform (replace import + call),
edx-enterprise (new pipeline step)

**Dependencies:** None. Good first epic.

---

### 02_user_account_readonly_fields

**Current location:**
- `openedx-platform/openedx/core/djangoapps/user_api/accounts/api.py`
  - `update_account_settings(requesting_user, update, username=None)` function
  - Line ~41: `from openedx.features.enterprise_support.utils import get_enterprise_readonly_account_fields`
  - Line ~200: `get_enterprise_readonly_account_fields(user)` — returns list of readonly field names
- `openedx-platform/openedx/features/enterprise_support/utils.py`
  - `get_enterprise_readonly_account_fields(user)` — checks if user is enterprise SSO learner
    and returns `settings.ENTERPRISE_READONLY_ACCOUNT_FIELDS` if so, else `[]`

**Migration approach:** New openedx-filter (AccountSettingsReadOnlyFieldsRequested).
Explicitly called out in CLAUDE.md notes. Do NOT use the existing
`AccountSettingsRenderStarted` filter.

**New filter:** `AccountSettingsReadOnlyFieldsRequested` in `openedx_filters/learning/filters.py`
- Signature: `run_filter(editable_fields, user)` → returns modified `editable_fields` list
- Filter type: `"org.openedx.learning.account.settings.read_only_fields.requested.v1"`
- No exception class needed

**edx-enterprise step:** Checks if user is linked to an enterprise SSO IdP; if so, removes
fields in `settings.ENTERPRISE_READONLY_ACCOUNT_FIELDS` from `editable_fields`.

**Repos touched:** openedx-filters (new filter), openedx-platform (replace import + call),
edx-enterprise (new pipeline step)

**Dependencies:** None. Good first epic alongside grades enrichment.

---

### 03_discount_enterprise_learner_exclusion

**Current location:**
- `openedx-platform/openedx/features/discounts/applicability.py`
  - `can_receive_discount(user, course)` (line ~129): lazy import of `is_enterprise_learner`
  - Another function (line ~183): same lazy import of `is_enterprise_learner`
  - Both call `is_enterprise_learner(user)` and return `False` (no discount) if true
- `openedx-platform/openedx/features/enterprise_support/utils.py`
  - `is_enterprise_learner(user)` — checks cache, then queries `EnterpriseCustomerUser`

**Migration approach:** New openedx-filter that allows plugins to mark a user as ineligible
for discounts.

**New filter:** `DiscountEligibilityCheckRequested` in `openedx_filters/learning/filters.py`
- Signature: `run_filter(user, course_key, is_eligible)` → returns modified `is_eligible` bool
- Filter type: `"org.openedx.learning.discount.eligibility.check.requested.v1"`

**edx-enterprise step:** Returns `{"is_eligible": False}` if `is_enterprise_learner(user)`.

**Repos touched:** openedx-filters (new filter), openedx-platform (replace import + call),
edx-enterprise (new pipeline step)

**Dependencies:** None.

---

### 04_user_retirement_enterprise_cleanup

**Current location:**
- `openedx-platform/openedx/core/djangoapps/user_api/accounts/views.py`
  - Line 13: `from consent.models import DataSharingConsent`
  - Line 28: `from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser, PendingEnterpriseCustomerUser`
  - `retire_users_data_sharing_consent(username, retired_username)` (line ~1213):
    Queries `EnterpriseCustomerUser` → iterates `EnterpriseCourseEnrollment` → calls
    `DataSharingConsent.objects.retire_user()` and `HistoricalDataSharingConsent`
  - `retire_user_from_pending_enterprise_customer_user(user, retired_email)` (line ~1235):
    Updates `PendingEnterpriseCustomerUser` with retired_email
  - Both methods called from within the retirement view at lines ~1158-1161
  - Line 1173: `USER_RETIRE_LMS_CRITICAL.send(sender=self.__class__, user=user)` — also
    used by line 1310-1311 to declare consent model fields for retirement framework
  - Line ~1095: `USER_RETIRE_LMS_MISC.send(...)` — sent before the enterprise-specific calls

**Migration approach:** Enhance the existing `USER_RETIRE_LMS_CRITICAL` Django signal
(per CLAUDE.md notes). The signal currently sends `user=user`; add `retired_username` and
`retired_email` kwargs. Remove the two enterprise methods from views.py entirely.
Also remove the model retirement declarations at lines 1310-1311.

**Signal changes:** In `openedx-platform/openedx/core/djangoapps/user_api/accounts/signals.py`,
`USER_RETIRE_LMS_CRITICAL = Signal()` already exists. The send call must add:
```python
USER_RETIRE_LMS_CRITICAL.send(
    sender=self.__class__,
    user=user,
    retired_username=retired_username,
    retired_email=retired_email,
)
```
(These local vars are already computed before this line in the retirement view.)

**edx-enterprise handler:** Connects to `USER_RETIRE_LMS_CRITICAL` and performs both
retirement operations (DataSharingConsent retire, PendingEnterpriseCustomerUser update).
Also registers consent model fields with the retirement framework via edx-enterprise's own
retirement config (not openedx-platform).

**Repos touched:** openedx-platform (remove imports + enterprise methods, enhance signal send),
edx-enterprise (new signal handler)

**Dependencies:** None (signal already exists; this is additive).

---

### 05_enterprise_username_change_command

**Current location:**
- `openedx-platform/common/djangoapps/student/management/commands/change_enterprise_user_username.py`
  - Direct import of enterprise models (username change management command)
  - This command exists solely to change enterprise user usernames for testing

**Migration approach:** Move the management command entirely into edx-enterprise.
It has no non-enterprise use case.

**Repos touched:** openedx-platform (remove command file + tests),
edx-enterprise (add management command)

**Dependencies:** None.

---

### 06_dsc_courseware_view_redirects

**Current location:**
- `openedx-platform/lms/djangoapps/courseware/views/index.py`
  - Line 26: `from openedx.features.enterprise_support.api import data_sharing_consent_required`
  - Line 47: `@method_decorator(data_sharing_consent_required)` on `CoursewareIndex`
- `openedx-platform/lms/djangoapps/courseware/views/views.py`
  - Line 154: same import
  - Line 531: `@method_decorator(data_sharing_consent_required)` on `CourseTabView`
  - Line 980: `@data_sharing_consent_required` on `jump_to_id` view function
- `openedx-platform/openedx/features/enterprise_support/api/course_wiki/views.py`
  — actually `openedx-platform/lms/djangoapps/course_wiki/views.py`
  - Line 20: same import
  - Line 34: `@data_sharing_consent_required` on `WikiView`
- `openedx-platform/lms/djangoapps/course_wiki/middleware.py`
  - Line 15: `from openedx.features.enterprise_support.api import get_enterprise_consent_url`
  - Line ~100: calls `get_enterprise_consent_url(request, str(course_id), source='WikiAccessMiddleware')`
    and redirects if truthy
- `openedx-platform/lms/djangoapps/courseware/access_utils.py`
  - Line 11: `from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser`
  - Line 73: `enterprise_learner_enrolled(request, user, course_key)` — queries enterprise
    models to determine if learner should redirect to enterprise portal
  - Line ~93: lazy import `enterprise_customer_from_session_or_learner_data`
  - Line 233: `check_data_sharing_consent(course_id)` — lazy import `get_enterprise_consent_url`,
    returns consent URL or None
  - Line ~161: calls `enterprise_learner_enrolled()` inside `_has_access_to_course()`

**Migration approach:** New `CoursewareViewRedirectURL` openedx-filter (per CLAUDE.md notes).
Replace the `data_sharing_consent_required` decorator with a new generic
`courseware_view_redirect` decorator that calls the filter and redirects to the first URL
returned, or passes if empty list.

The `enterprise_learner_enrolled` function and `check_data_sharing_consent` are also replaced
by filter calls. The enterprise_learner_enrolled redirect uses a separate invocation path
(inside `_has_access_to_course`), which could be the same filter.

**New filter:** `CoursewareViewRedirectURL` in `openedx_filters/learning/filters.py`
- Signature: `run_filter(redirect_urls, request, course_id)` → returns modified `redirect_urls` list
- Filter type: `"org.openedx.learning.courseware.view.redirect_url.requested.v1"`
- No exception needed (fail_silently=True, caller selects first URL)

**New decorator** (openedx-platform): `courseware_view_redirect` replaces
`data_sharing_consent_required`. Calls the filter, redirects to `redirect_urls[0]` if non-empty.

**edx-enterprise steps:**
- `ConsentRedirectStep`: checks if DSC consent is required for course, returns consent URL
- `LearnerPortalRedirectStep`: checks if enterprise learner enrolled via portal, returns portal URL

**Repos touched:** openedx-filters (new filter), openedx-platform (new decorator, replace
all usages in views + middleware + access_utils, remove enterprise model imports),
edx-enterprise (new pipeline steps)

**Dependencies:** None, but this is the largest and most complex epic.

**Note:** `access_utils.py` line 11 imports enterprise models directly — remove them by
moving the DB queries into the edx-enterprise pipeline step.

---

### 07_third_party_auth_enterprise_pipeline

**Current location:**
- `openedx-platform/common/djangoapps/third_party_auth/settings.py`
  - Line 15: `from openedx.features.enterprise_support.api import insert_enterprise_pipeline_elements`
  - Line ~74: `insert_enterprise_pipeline_elements(django_settings.SOCIAL_AUTH_PIPELINE)` called
    from `apply_settings()` — injects enterprise pipeline stages into SOCIAL_AUTH_PIPELINE
- `openedx-platform/common/djangoapps/third_party_auth/pipeline.py`
  - Line 99: `from enterprise.models import ... is_enterprise_customer_user` (via utils import)
    Actually: line 793: lazy import `from openedx.features.enterprise_support.api import enterprise_is_enabled`
  - Lines 802-855: `associate_by_email_if_enterprise_user()` inner function, decorated with
    `@enterprise_is_enabled()`, calls `is_enterprise_customer_user(current_provider.provider_id, current_user)` from enterprise models via `third_party_auth/utils.py`
- `openedx-platform/common/djangoapps/third_party_auth/saml.py`
  - Line 144-148: `SAMLAuth.disconnect()` override — lazy import
    `from openedx.features.enterprise_support.api import unlink_enterprise_user_from_idp`,
    then calls it
- `openedx-platform/common/djangoapps/third_party_auth/utils.py`
  - Line 14: `from enterprise.models import EnterpriseCustomerIdentityProvider, EnterpriseCustomerUser`
  - `is_enterprise_customer_user(provider_id, user)` (line ~238): queries these models

**Migration approach:** Multi-part. Three distinct behaviors:

1. **Pipeline injection** (`insert_enterprise_pipeline_elements`): Replace with plugin
   settings — edx-enterprise adds its pipeline stages to `SOCIAL_AUTH_PIPELINE` via
   `plugin_settings()` callback, eliminating the need for `insert_enterprise_pipeline_elements`
   and the `third_party_auth/settings.py` import.

2. **Associate-by-email** (`associate_by_email_if_enterprise_user`): This is already a
   pipeline stage logic. The entire inner function can be moved into an edx-enterprise
   SAML pipeline step registered via `SOCIAL_AUTH_PIPELINE` in edx-enterprise plugin_settings.
   The platform-side code simply removes the function and its imports.

3. **SAML disconnect** (`SAMLAuth.disconnect`): Emit a new Django signal
   `SocialAuthAccountDisconnected` (or reuse existing `social_django` disconnect signal if
   available). edx-enterprise listens and calls `unlink_enterprise_user_from_idp`.

   Check `social_django` for existing `disconnect` signals before creating a new one:
   `grep -r "disconnect" openedx-platform/common/djangoapps/third_party_auth/ --include="*.py"`

**Repos touched:** openedx-platform (remove all enterprise imports from utils.py,
pipeline.py, saml.py, settings.py), edx-enterprise (new pipeline step + signal handler +
plugin_settings additions)

**Dependencies:** The settings/pipeline injection approach requires understanding of
how `plugin_settings` works; review `edx-django-utils/edx_django_utils/plugins/plugin_settings.py`.

---

### 08_saml_admin_enterprise_views

**Current location:**
- `openedx-platform/common/djangoapps/third_party_auth/samlproviderconfig/views.py`
  - Line 12: `from enterprise.models import EnterpriseCustomerIdentityProvider, EnterpriseCustomer`
  - `SAMLProviderConfigViewSet` — entire view gated on `permission_required = 'enterprise.can_access_admin_dashboard'`
  - Queries `EnterpriseCustomerIdentityProvider` throughout
- `openedx-platform/common/djangoapps/third_party_auth/samlproviderdata/views.py`
  - Line 11: `from enterprise.models import EnterpriseCustomerIdentityProvider`
  - `SAMLProviderDataViewSet` — same enterprise RBAC permission
  - Queries `EnterpriseCustomerIdentityProvider`

**Migration approach:** These views exist solely to serve enterprise admin functionality
and have no non-enterprise use case. Move them into edx-enterprise as enterprise admin
API views, exposing the same REST API endpoints but hosted within edx-enterprise's URL
namespace. Remove from openedx-platform entirely (including URL registrations in
`openedx-platform/lms/urls.py` if applicable).

Check URL registrations: `grep -n "samlproviderconfig\|samlproviderdata"
openedx-platform/lms/urls.py openedx-platform/common/djangoapps/third_party_auth/urls.py`

**Repos touched:** openedx-platform (remove views + URL registrations),
edx-enterprise (add equivalent views under enterprise admin URLs)

**Dependencies:** Epic 18 (plugin registration) should be done alongside or after this
epic so that the `enterprise.urls` inclusion handles the new view URLs.

---

### 09_logistration_enterprise_context

**Current location:**
- `openedx-platform/openedx/core/djangoapps/user_authn/views/login_form.py`
  - Lines 31-34: imports `enterprise_customer_for_request`, `enterprise_enabled`,
    `get_enterprise_slug_login_url`, `handle_enterprise_cookies_for_logistration`,
    `update_logistration_context_for_enterprise`
  - Line ~59: `if current_provider and enterprise_customer_for_request(request):`
  - Lines ~203-283: enterprise customer lookup, conditional form context, sidebar context,
    cookie handling — all gating on `enterprise_customer_for_request(request)`
- `openedx-platform/openedx/core/djangoapps/user_authn/views/registration_form.py`
  - Line 36: `from openedx.features.enterprise_support.api import enterprise_customer_for_request`
  - Line ~1147: `enterprise_customer_for_request(request)` gates SSO registration form skip
- `openedx-platform/openedx/core/djangoapps/user_authn/views/login.py`
  - Line 63: imports `activate_learner_enterprise`, `get_enterprise_learner_data_from_api`
  - `enterprise_selection_page(request, user, next_url)` function (line ~481): checks
    enterprise learner data, redirects to enterprise selection page or auto-activates
  - Line ~652: calls `enterprise_selection_page(request, user, url)`

**Migration approach:** Multi-part, use existing openedx-filters where possible.

1. **Login form context**: Extend existing `StudentLoginRequested` filter (already defined
   in `openedx_filters/learning/filters.py`) to enrich the context with enterprise customer
   data. If the filter signature doesn't accommodate it, create a new
   `LogistrationContextRequested` filter.

2. **Registration form field filtering**: Use existing `StudentRegistrationRequested` filter
   to remove fields for enterprise SSO users (filter step checks enterprise customer, removes
   excluded fields from form).

3. **Login enterprise selection redirect**: New signal `UserLoginCompleted` or use existing
   post-auth mechanisms; edx-enterprise listens and handles the enterprise selection redirect.
   Check if `StudentLoginRequested` can redirect via exception (it has a
   `RedirectToPage` exception).

   Alternatively, create a `PostLoginRedirectURLRequested` filter that returns an optional
   redirect URL after successful login.

**Affected functions in enterprise_support:**
- `enterprise_customer_for_request(request)` in `enterprise_support/api.py`
- `update_logistration_context_for_enterprise(request, context, enterprise_customer)` in `enterprise_support/utils.py`
- `handle_enterprise_cookies_for_logistration(request, response, context)` in `enterprise_support/utils.py`
- `get_enterprise_slug_login_url()` in `enterprise_support/utils.py`
- `activate_learner_enterprise(request, user, enterprise_customer)` in `enterprise_support/api.py`
- `get_enterprise_learner_data_from_api(user)` in `enterprise_support/api.py`

**Repos touched:** openedx-filters (new filters if needed), openedx-platform (replace
all imports + calls with filter/signal invocations), edx-enterprise (new pipeline steps)

**Dependencies:** None, but complex — may be split into sub-epics per view file.

---

### 10_student_dashboard_enterprise_context

**Current location:**
- `openedx-platform/common/djangoapps/student/views/dashboard.py`
  - Lines 51-54: imports `get_dashboard_consent_notification`,
    `get_enterprise_learner_portal_context` from `enterprise_support.api`;
    `is_enterprise_learner` from `enterprise_support.utils`
  - Line ~620: `enterprise_message = get_dashboard_consent_notification(request, user, course_enrollments)`
  - Lines ~802-803: `'enterprise_message': enterprise_message, 'consent_required_courses': ...`
    added to template context
  - Lines ~854-859: `is_enterprise_user`, enterprise learner portal context added to context
- `openedx-platform/common/djangoapps/student/views/management.py`
  - Line 67: `from openedx.features.enterprise_support.utils import is_enterprise_learner`
  - Line ~212: `'is_enterprise_learner': is_enterprise_learner(user)` in context
  - Line ~685: `redirect(redirect_url) if redirect_url and is_enterprise_learner(request.user) else redirect('dashboard')`

**Migration approach:** Use existing `DashboardRenderStarted` filter
(defined in `openedx_filters/learning/filters.py`). This filter has a `context` parameter
that pipeline steps can enrich.

- Add a pipeline step that enriches the dashboard context with `enterprise_message`,
  `consent_required_courses`, `is_enterprise_user`, and `enterprise_learner_portal_*` keys.
- For `management.py` `is_enterprise_learner` usage: create a new small filter or use
  a Django signal.

**Affected enterprise_support functions:**
- `get_dashboard_consent_notification(request, user, course_enrollments)` in `api.py`
- `get_enterprise_learner_portal_context(request)` in `api.py`
- `is_enterprise_learner(user)` in `utils.py`

**Repos touched:** openedx-platform (remove imports, call existing filter),
edx-enterprise (new DashboardRenderStarted pipeline step)

**Dependencies:** Depends on `DashboardRenderStarted` already being invoked in the
platform (verify: `grep -n "DashboardRenderStarted" openedx-platform/common/djangoapps/student/views/dashboard.py`).
If not yet invoked, add invocation as part of this epic.

---

### 11_enrollment_api_enterprise_support

**Current location:**
- `openedx-platform/openedx/core/djangoapps/enrollments/views.py`
  - Lines 60-64: imports `EnterpriseApiServiceClient`, `ConsentApiServiceClient`,
    `enterprise_enabled` from `enterprise_support.api`
  - Lines ~777-796: When `explicit_linked_enterprise` param is provided and `enterprise_enabled()`,
    calls `EnterpriseApiServiceClient.post_enterprise_course_enrollment()` and
    `ConsentApiServiceClient.provide_consent()` after enrollment

**Migration approach:** New `CourseEnrollmentStarted` pipeline step. The existing
`CourseEnrollmentStarted` filter is already defined in openedx-filters. Add a new step
in edx-enterprise that, when an enterprise UUID is included in the enrollment data,
posts the enrollment to the enterprise API and records consent.

The `explicit_linked_enterprise` and `enterprise_uuid` enrollment parameters need to flow
through the filter as part of the enrollment context dict.

**Repos touched:** openedx-platform (remove imports, pass enterprise_uuid through
existing filter), edx-enterprise (new CourseEnrollmentStarted pipeline step)

**Dependencies:** None.

---

### 12_learner_home_enterprise_dashboard

**Current location:**
- `openedx-platform/lms/djangoapps/learner_home/views.py`
  - Lines 63-65: imports `enterprise_customer_from_session_or_learner_data`,
    `get_enterprise_learner_data_from_db`
  - `get_enterprise_customer(user, request, is_masquerading)` (line ~212): returns enterprise
    customer dict or None; used to populate `enterpriseDashboard` key in response (line ~551)

**Migration approach:** Use a pluggable override for `get_enterprise_customer`. Since there
is only ever one enterprise plugin installed at a time, a pluggable override is sufficient
and simpler than a filter pipeline.

Decorate `get_enterprise_customer` with `@pluggable_override` (see
`edx-django-utils/edx_django_utils/plugins/pluggable_override.py`). The default
implementation returns `None`. edx-enterprise provides the override that calls
`enterprise_customer_from_session_or_learner_data` or `get_enterprise_learner_data_from_db`
depending on whether the request is masquerading.

**Repos touched:** openedx-platform (remove imports, add `@pluggable_override` decorator),
edx-enterprise (override implementation)

**Dependencies:** None.

---

### 13_course_home_progress_enterprise_name

**Current location:**
- `openedx-platform/lms/djangoapps/course_home_api/progress/views.py`
  - Line 42: `from openedx.features.enterprise_support.utils import get_enterprise_learner_generic_name`
  - Line ~209: `username = get_enterprise_learner_generic_name(request) or student.username`

**Migration approach:** Introduce an intermediate `obfuscated_username(request, student)`
function in `views.py` and decorate it with `@pluggable_override`. Since only one plugin
can logically override a username at a time, a pluggable override is appropriate here.

The default implementation returns `None`. Replace line ~209 with:
```python
username = obfuscated_username(request, student) or student.username
```
edx-enterprise provides the override that calls `get_enterprise_learner_generic_name(request)`
and returns the generic name if the learner is an enterprise user, otherwise `None`.

**Repos touched:** openedx-platform (remove import, introduce `obfuscated_username` with
`@pluggable_override`), edx-enterprise (override implementation)

**Dependencies:** None.

---

### 14_course_modes_enterprise_customer

**Current location:**
- `openedx-platform/common/djangoapps/course_modes/views.py`
  - Line 42: `from openedx.features.enterprise_support.api import enterprise_customer_for_request`
  - Also imports `EnterpriseApiServiceClient`, `ConsentApiServiceClient` (from enterprise_support)
  - Lines ~191-197: If an enterprise customer is found for the request and the course mode has
    a SKU, logs and uses enterprise context for the ecommerce calculate API call

**Migration approach:** New filter `CourseModeCheckoutContextRequested` or reuse an
existing filter. The filter enriches the checkout context with the enterprise customer UUID,
allowing the ecommerce integration to apply enterprise pricing.

**New filter:** `CourseModeCheckoutStarted` in `openedx_filters/learning/filters.py`
- Signature: `run_filter(context, request, course_mode)` → returns enriched context
- Filter type: `"org.openedx.learning.course_mode.checkout.started.v1"`

**edx-enterprise step:** Injects enterprise customer info into context.

**Repos touched:** openedx-filters (new filter), openedx-platform (replace import),
edx-enterprise (new pipeline step)

**Dependencies:** None.

---

### 15_support_views_enterprise_context

**Current location:**
- `openedx-platform/lms/djangoapps/support/views/contact_us.py`
  - Line 14: `from openedx.features.enterprise_support import api as enterprise_api`
  - Lines ~49-51: `enterprise_api.enterprise_customer_for_request(request)` — adds
    `'enterprise_learner'` tag to support ticket if user is enterprise
- `openedx-platform/lms/djangoapps/support/views/enrollments.py`
  - Lines 37-42: imports `enterprise_enabled`, `get_data_sharing_consents`,
    `get_enterprise_course_enrollments` from `enterprise_support.api`;
    `EnterpriseCourseEnrollmentSerializer` from `enterprise_support.serializers`
  - `_enterprise_course_enrollments_by_course_id(user)` (line ~74): queries enterprise
    enrollments and consent records, serializes them for the support view

**Migration approach:** Two separate behaviors:

1. **contact_us.py**: New filter `SupportTicketTagsRequested` or a Django signal. A filter
   is cleaner since we need tags returned.

2. **enrollments.py**: This is support tooling for viewing enterprise enrollment data.
   Since it queries enterprise models, the entire `_enterprise_course_enrollments_by_course_id`
   method should be replaced with a filter call that edx-enterprise populates with the
   enterprise enrollment data.

**New filters:**
- `SupportContactContextRequested` — enriches support contact context with tags
- `SupportEnrollmentDataRequested` — provides enterprise enrollment data for support view

**Repos touched:** openedx-filters (new filters), openedx-platform (replace imports),
edx-enterprise (new pipeline steps)

**Dependencies:** None.

---

### 16_programs_api_enterprise_enrollments

**Current location:**
- `openedx-platform/openedx/core/djangoapps/programs/rest_api/v1/views.py`
  - Line 19: imports `get_enterprise_course_enrollments`, `enterprise_is_enabled`
    from `enterprise_support.api`
  - `CourseRunProgressView._get_enterprise_course_enrollments(enterprise_uuid, user)` (line ~181):
    decorated `@enterprise_is_enabled(otherwise=EmptyQuerySet)`; queries enterprise
    course enrollments filtered by enterprise UUID
  - Line ~93-94: calls this method when `enterprise_uuid` param is in request

**Migration approach:** Use a pluggable override for `_get_enterprise_course_enrollments`.
Since there is only ever one enterprise plugin installed at a time, the filter pipeline
mechanism adds unnecessary complexity; a pluggable override is sufficient.

Decorate `_get_enterprise_course_enrollments` with `@pluggable_override` (see
`edx-django-utils/edx_django_utils/plugins/pluggable_override.py`). The default
implementation returns an empty queryset. edx-enterprise provides the override
implementation that queries enterprise course enrollments filtered by enterprise UUID.
Remove the `enterprise_is_enabled` import and decorator entirely; when edx-enterprise is
not installed, the default empty-queryset implementation is used automatically.

**Repos touched:** openedx-platform (replace import + add `@pluggable_override` decorator),
edx-enterprise (override implementation)

**Dependencies:** None.

### 17_enterprise_support_to_edx_enterprise

**Background and motivation:**
The `openedx/features/enterprise_support/` module lives inside openedx-platform but imports
directly from `enterprise` and `consent` (edx-enterprise packages). Epics 01-16 replace every
external caller of enterprise_support with filter/signal hooks; the resulting edx-enterprise
plugin steps call enterprise_support functions internally. However, enterprise_support itself
still exists in openedx-platform and still imports from edx-enterprise. This makes edx-enterprise
a mandatory dependency of openedx-platform: any deployment without edx-enterprise installed would
fail at import time when Django loads enterprise_support. Therefore, enterprise_support must be
fully removed from openedx-platform before edx-enterprise can become a truly optional plugin.

**What enterprise_support contains (all must move):**
- `api.py` (~1075 lines): API client classes (`EnterpriseApiClient`, `ConsentApiClient`,
  `EnterpriseApiServiceClient`, `ConsentApiServiceClient`); enterprise customer lookup, DSC
  check, consent URL generation, learner data, portal context, dashboard notification, SSO
  helpers, and the `data_sharing_consent_required` decorator and `enterprise_is_enabled`
  decorator (the latter still referenced by some edx-enterprise plugin steps)
- `utils.py`: `is_enterprise_learner`, `get_enterprise_readonly_account_fields`,
  `get_enterprise_learner_generic_name`, `get_enterprise_slug_login_url`,
  `handle_enterprise_cookies_for_logistration`, `update_logistration_context_for_enterprise`,
  `get_enterprise_sidebar_context`, and cache key helpers
- `context.py`: `get_enterprise_event_context`
- `signals.py`: handlers for `COURSE_GRADE_NOW_PASSED`, `COURSE_ASSESSMENT_GRADE_CHANGED`,
  `UNENROLL_DONE` (platform signals), and `post_save`/`pre_save` on enterprise models
- `tasks.py`: `clear_enterprise_customer_data_consent_share_cache` Celery task
- `serializers.py`: `EnterpriseCourseEnrollmentSerializer`
- `admin/`: `EnrollmentAttributeOverrideView`, `CSVImportForm`
- `enrollments/utils.py`: `lms_update_or_create_enrollment`
- `templates/enterprise_support/enterprise_consent_declined_notification.html`
- All test files under `enterprise_support/tests/`

**Migration approach:** Move the enterprise_support package wholesale into edx-enterprise under
a new internal namespace (e.g., `enterprise/platform_support/`). Update all edx-enterprise
plugin steps created in epics 01-16 to use internal imports rather than
`from openedx.features.enterprise_support...`. Move the signal handler activations into
edx-enterprise's `AppConfig.ready()`. Delete the `openedx/features/enterprise_support/`
directory from openedx-platform and remove its `INSTALLED_APPS` entry from
`lms/envs/common.py`.

**Steps:**

1. **[edx-enterprise]** Copy the full enterprise_support package into edx-enterprise
   (e.g., `enterprise/platform_support/`). Update all internal imports within the copied
   files to reflect the new module path. Add signal handler activations to edx-enterprise's
   existing `AppConfig.ready()`.

2. **[edx-enterprise]** Update all plugin step files created in epics 01-16 to import from
   the new internal path instead of `openedx.features.enterprise_support`.

3. **[openedx-platform]** Delete `openedx/features/enterprise_support/` in its entirety.
   Remove `'openedx.features.enterprise_support.apps.EnterpriseSupportConfig'` from
   `INSTALLED_APPS` in `lms/envs/common.py`. Remove the corresponding test removal
   from `lms/envs/test.py` if present.

**Repos touched:** edx-enterprise (copy module, update plugin step imports, activate
signal handlers in AppConfig), openedx-platform (delete module, remove INSTALLED_APPS entry)

**Dependencies:** Blocked by all epics 01-16. Every external caller of enterprise_support
must be replaced by a hook before this epic ships, because this epic deletes the module.
This epic in turn blocks epic 18 (plugin registration): edx-enterprise cannot
be made optional while enterprise_support still exists in openedx-platform.

**Note:** The edx-enterprise plugin steps created in epics 01-16 will temporarily call
`from openedx.features.enterprise_support...` until this epic ships. This is acceptable
because during that window edx-enterprise is still a mandatory dependency. This epic
atomically cuts over all those imports to internal paths.

---

### 18_plugin_registration

**Current location — settings (`lms/envs/common.py`):**
- Lines 48-61: `from enterprise.constants import (ENTERPRISE_ADMIN_ROLE, ENTERPRISE_LEARNER_ROLE, ...)`
  — 9 role constants imported at module level (blocking import)
- Line 520: `ENABLE_ENTERPRISE_INTEGRATION = False`
- Line 600: `ALLOW_ADMIN_ENTERPRISE_COURSE_ENROLLMENT_DELETION = False`
- Line ~1169: `'enterprise.middleware.EnterpriseLanguagePreferenceMiddleware'` in MIDDLEWARE
- Lines 2586-3017 (approx): All `ENTERPRISE_*` settings:
  - `ENTERPRISE_PUBLIC_ENROLLMENT_API_URL`, `ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES`
  - `ENTERPRISE_SUPPORT_URL`, `ENTERPRISE_CUSTOMER_SUCCESS_EMAIL`, `ENTERPRISE_INTEGRATIONS_EMAIL`
  - `ENTERPRISE_API_URL`, `ENTERPRISE_CONSENT_API_URL`, `ENTERPRISE_CUSTOMER_LOGO_IMAGE_SIZE`
  - `ENTERPRISE_ALL_SERVICE_USERNAMES`
  - `ENTERPRISE_PLATFORM_WELCOME_TEMPLATE`, `ENTERPRISE_SPECIFIC_BRANDED_WELCOME_TEMPLATE`
  - `ENTERPRISE_PROXY_LOGIN_WELCOME_TEMPLATE`, `ENTERPRISE_TAGLINE`
  - `ENTERPRISE_EXCLUDED_REGISTRATION_FIELDS`, `ENTERPRISE_READONLY_ACCOUNT_FIELDS`
  - `ENTERPRISE_CUSTOMER_COOKIE_NAME`, `ENTERPRISE_VSF_UUID`
  - `ENTERPRISE_MANUAL_REPORTING_CUSTOMER_UUIDS`
- Lines ~2670-2693: `SYSTEM_WIDE_ROLE_CLASSES` enterprise role mappings (uses imported constants)

**Current location — app/URL registration:**
- `openedx/envs/common.py`: `('enterprise', None)` and `('consent', None)` listed in
  `OPTIONAL_APPS` (lines ~767-768) under the "Enterprise Apps" comment block
  (the `EnterpriseSupportConfig` entry is already removed by epic 17)
- `lms/urls.py` line ~881: conditional `enterprise.urls` inclusion

**Migration approach:**

All three Django apps in edx-enterprise (`enterprise`, `consent`, `enterprise_support`) are
registered as separate openedx plugins. Following the naming convention from
`openedx-platform/openedx/core/djangoapps/password_policy/`, each app gets a `plugin_app`
dict in its `AppConfig` and a `plugin_settings(settings)` callback in its own
`{app}/settings/common.py` file.

Settings are distributed across the three plugins by ownership:

- **`enterprise/settings/common.py`**: All core `ENTERPRISE_*` settings (excluding the two
  below), `SYSTEM_WIDE_ROLE_CLASSES` role mappings (using edx-enterprise's own constants —
  no platform import needed), `EnterpriseLanguagePreferenceMiddleware` appended to
  `MIDDLEWARE`, `SOCIAL_AUTH_PIPELINE` additions (TPA pipeline steps from epic 07), all
  `OPEN_EDX_FILTERS_CONFIG` filter step registrations (epics 09-11, 14-15), and all
  pluggable override settings (epics 12, 13, 16).
  - `ENTERPRISE_PUBLIC_ENROLLMENT_API_URL` and `ENTERPRISE_API_URL` are derived from
    `settings.LMS_ROOT_URL` (replacing the `Derived(lambda s: ...)` pattern used in common.py).

- **`consent/settings/common.py`**: `ENTERPRISE_CONSENT_API_URL` (derived from
  `settings.LMS_ROOT_URL`).

- **`enterprise_support/settings/common.py`**: `ENTERPRISE_READONLY_ACCOUNT_FIELDS` and
  `ENTERPRISE_CUSTOMER_COOKIE_NAME`, which are consumed by enterprise_support utility
  functions.

Steps:

1. **[edx-enterprise]** Add `plugin_app` configuration to `EnterpriseConfig`, `ConsentConfig`,
   and a new `EnterpriseSupportConfig` in edx-enterprise, each declaring `ProjectType.LMS`
   settings config (pointing to their respective `settings.common`) and, where applicable,
   URL config.

2. **[edx-enterprise]** Implement `plugin_settings(settings)` in each app's
   `{app}/settings/common.py` as described above, using `setdefault` throughout so operator
   overrides are respected.

3. **[openedx-platform]** Remove the `from enterprise.constants import ...` block, all
   `ENTERPRISE_*` settings, enterprise entries from `SYSTEM_WIDE_ROLE_CLASSES`, and the
   `EnterpriseLanguagePreferenceMiddleware` entry from `lms/envs/common.py`.

4. **[openedx-platform]** Remove `('enterprise', None)` and `('consent', None)` from
   `OPTIONAL_APPS` in `openedx/envs/common.py`. The plugin framework adds both automatically
   when edx-enterprise is installed.

5. **[openedx-platform]** Remove the conditional `enterprise.urls` inclusion from
   `lms/urls.py`; edx-enterprise registers its URLs via `plugin_app` config instead.

Review `edx-django-utils/edx_django_utils/plugins/` for the `plugin_app` API and how
`plugin_settings` callbacks are structured and invoked.

**Repos touched:** openedx-platform (remove enterprise.constants import, all ENTERPRISE_*
settings, OPTIONAL_APPS entries for enterprise and consent, conditional URL include),
edx-enterprise (plugin_app configs and plugin_settings callbacks across all three apps)

**Dependencies:** Blocked by epic 17 (enterprise_support module migration), which ensures
that no part of openedx-platform imports from enterprise or enterprise_support packages,
making it safe to remove the hard-coded app registration and settings. Epics 01-16 must
also be complete. Per CLAUDE.md: "Registering edx-enterprise as a proper openedx plugin
should happen only after all enterprise/consent imports have been removed from
openedx-platform."

---

## Epic Sequencing Summary

**Epics with no dependencies (can start immediately, in parallel):**
- 01 Grades analytics event enrichment
- 02 User account readonly fields
- 03 Discount enterprise learner exclusion
- 04 User retirement enterprise cleanup
- 05 Enterprise username change command

**Epics with no code dependencies but medium complexity (start after initial epics ship):**
- 11 Enrollment API enterprise support
- 12 Learner home enterprise dashboard
- 13 Course home progress enterprise name
- 14 Course modes enterprise customer
- 15 Support views enterprise context
- 16 Programs API enterprise enrollments

**Epics with higher complexity or cross-cutting concerns:**
- 06 DSC courseware view redirects (largest; replaces decorator across 4+ files)
- 07 Third-party auth enterprise pipeline (multi-part; SAML pipeline stages)
- 08 SAML admin enterprise views (views to be moved to edx-enterprise)
- 09 Logistration enterprise context (complex; multiple auth views)
- 10 Student dashboard enterprise context (depends on DashboardRenderStarted being invoked)

**Final epics (strict order):**
- 17 Enterprise support module migration (blocked by 01-16; deletes enterprise_support from platform)
- 18 Plugin registration (blocked by 17; includes settings migration via plugin_settings())

---

## Additional Notes for Second-Pass AI

### Test file handling
For every production file change, the corresponding test file also imports enterprise modules
(e.g. `test_access.py`, `test_views.py`, `test_retirement_views.py`). Each diff must update
test files to mock the filter/signal interface instead of mocking enterprise functions directly.

### enterprise_support module fate
As epics 01-16 ship, the functions in `openedx/features/enterprise_support/api.py` and
`utils.py` will be called only from edx-enterprise plugin steps — no longer from
openedx-platform directly. However, enterprise_support itself still imports from
`enterprise` and `consent`, making edx-enterprise a mandatory platform dependency.
Epic 17 resolves this by moving the entire module into edx-enterprise and deleting it
from the platform. Until epic 17 ships, edx-enterprise plugin steps may freely import
from `openedx.features.enterprise_support`; epic 17 atomically replaces those imports.

### enterprise_support internal imports
Within enterprise_support itself (signals.py, tasks.py, etc.), enterprise models are
imported. Those imports are intentional and move with the module in epic 17. Only imports
FROM OUTSIDE enterprise_support (in other openedx-platform packages) are targets for
epics 01-16.

### Existing filters to reuse
Before creating a new filter, check `openedx_filters/learning/filters.py` for:
- `DashboardRenderStarted` — use for epic 10
- `StudentLoginRequested` — consider for epic 09 (login form context)
- `StudentRegistrationRequested` — consider for epic 09 (registration form)
- `CourseEnrollmentStarted` — use for epic 11
- `AccountSettingsRenderStarted` — do NOT use for epic 02 (per CLAUDE.md)

### Filter config pattern
For `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py`, follow this structure:
```python
OPEN_EDX_FILTERS_CONFIG = {
    "org.openedx.learning.grade.context.requested.v1": {
        "fail_silently": True,
        "pipeline": [],
    },
    # ... other filters
}
```
And in `lms/envs/production.py`, add `'OPEN_EDX_FILTERS_CONFIG'` to the exclusion list
(line ~76), then add merge logic following the `TRACKING_BACKENDS` pattern (line ~273):
```python
for filter_type, config in _YAML_TOKENS.get('OPEN_EDX_FILTERS_CONFIG', {}).items():
    if filter_type in OPEN_EDX_FILTERS_CONFIG:
        OPEN_EDX_FILTERS_CONFIG[filter_type]['pipeline'].extend(
            config.get('pipeline', [])
        )
        if 'fail_silently' in config:
            OPEN_EDX_FILTERS_CONFIG[filter_type]['fail_silently'] = config['fail_silently']
    else:
        OPEN_EDX_FILTERS_CONFIG[filter_type] = config
```

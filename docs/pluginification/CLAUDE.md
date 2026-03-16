# Background

Currently, edx-enterprise is tightly coupled with openedx-platform through direct imports across
core modules, and edx-enterprise in general is a mandatory library. The
ENABLE_ENTERPRISE_INTEGRATION setting doesn't fully disable enterprise code paths or imports.

For operators: Customizing or forking edx-enterprise requires maintaining compatibility with
upstream module names and function signatures indefinitely. Enterprise code paths cannot be fully
switched off, increasing error surface area even for non-enterprise deployments.

For developers: Tight coupling obscures where enterprise code lives and creates risk of unintended
side-effect when modifying either enterprise or platform logic.

I am working on a project to convert the edx-enterprise library into an optional plugin by
leveraging the openedx plugin framework, openedx-filters, and django built-in features (including
middleware, signals, etc.) to replace enterprise-specific logic with generic plugin hooks and
migrate the custom enterprise logic to edx-enterprise.

* openedx plugin framework: edx-django-utils/edx_django_utils/plugins/
* openedx-filters: openedx-filters/

Our high-level approach to the project is to incrementally migrate small chunks of
enterprise-specific logic behind hooks, completely merging/deploying changes between each increment.
This project will span several months, and we do not want to accumulate unmerged changes over time.

The first chunks of work should all be focused on removing enterprise/consent
imports. Registering edx-enterprise as a proper openedx plugin should happen
only after all enterprise/consent imports have been removed from
openedx-platform.

The following openedx-platform modules import the enterprise module, and will be some of the main
targets for adding plugin hooks (non-exhaustive list):

* Third-party auth (openedx-platform/common/djangoapps/third_party_auth)
* Courseware access and DSC redirects (openedx-platform/lms/djangoapps/courseware)
* User API and retirement (openedx-platform/openedx/core/djangoapps/user_api)
* RBAC role mappings and other enterprise-specific settings (openedx-platform/lms/envs/common.py)

Any openedx-platform code which uses any module provided by the edx-enterprise repository is a
candidate for replacing with a plugin hook. These are the modules provided by edx-enterprise
relevant to this project:

* enterprise
* consent

Furthermore, the enterprise_support module (openedx-platform/openedx/features/enterprise_support/)
is so tightly coupled with edx-enterprise that we also plan to migrate it into edx-enterprise to
avoid extensive additions of enterprise hooks within that module. That means anywhere
openedx-platform imports from the enterprise_support module from outside the enterprise_support
module itself are also candidates for migration.

Finally, some settings in openedx-platform/lms/envs/ are enterprise-specific and should eventually
be migrated to the edx-enterprise repository, but only after all enterprise imports are removed from
openedx-platform.

After all work is done, the edx-enterprise repository should contain 3 openedx plugins:

* enterprise
* consent
* enterprise_support

These 3 plugins will existing alongside an orphaned deprecated
integrated_channels django app which is currently in the process of being
migrated to channel_integrations in the enterprise-integrated-channels/
repository. Do not worry about modifying that deprecated integrated_channels
module.

# Local git clones

You can freely read files within the following local git clones without prompting me:

* openedx-platform/
* edx-enterprise/
* enterprise-integrated-channels/
* edx-django-utils/
* openedx-filters/

If the local clone does not yet exist in the current working directory, you can clone it using:

```
git clone --depth 1 git@github.com:openedx/<repo>.git
```

# Selecting a migration approach

Enterprise-specific logic within openedx-platform can be migrated to the plugin using several
different approaches:

* Create a new openedx-filter and implement a new PipelineStep.
* Find an existing openedx-filter and implement a new PipelineStep.
* Create a new django signal and implement a new event handler.
* Find an existing django signal and implement a new event handler.
* Inject django middleware.
* Implement a pluggable override (edx-django-utils/edx_django_utils/plugins/pluggable_override.py)

Keep the following differences in mind:

* Filters can be more maintainable than pluggable overrides because we have no ability to stop
  multiple override implementations from overriding each other, whereas filters are structured as
  pipelines which run each implementation sequentially. It may be appropriate to use a pluggable
  override when the function being overridden can only be reasonably augmented once.
* Django signals can work best when no data payload needs to be passed between the sender and
  receiver, and require relatively few lines of code. Filters are designed to accommodate data
  passing, but require more code changes.
* Middleware are the easiest to install, but run on every request which has performance
  implications, especially for enterprise-specific logic which only impacts a small subset of
  requests.

Avoid creating multiple work chunks/epics to first "bake" enterprise settings into openedx-platform
then subsequently migrate them to edx-enterprise (via `plugin_settings()`). Just migrate all
enterprise settings as one single epic.

# Creating openedx filters

* Do not use "Enterprise" in filter class names, filter types, and filter exceptions.  Avoid even
  mentioning enterprise in any openedx-filters docstrings or openedx-filters code comments.
* For now, add new filter mappings to OPEN_EDX_FILTERS_CONFIG within
  `openedx-platform/lms/envs/common.py`. Never configure filter mappings via plugin_settings within
  edx-enterprise. Filter mappings added by this work will eventually be removed from
  openedx-platform common.py but not until the very end.
* Make sure openedx-platform/lms/envs/production.py will not override the setting if loaded
  from yaml. Adopt the pre-established pattern used by TRACKING_BACKENDS or CELERY_QUEUES which is
  to inhibit loading the OPEN_EDX_FILTERS_CONFIG into global namespace, then subsequently
  dynamically merge the setting value from yaml into the one imported from common.py. For each
  configured filter, pipeline steps loaded from yaml should be appended after any existing pipeline
  steps defined in common.py, and the `fail_silently` value from yaml takes precedence over the one
  from common.py.

# Migrating enterprise-specific settings

Defer migration of any enterprise-specific settings until one of the very last
epics to actually implment the openedx plugin framework within edx-enterprise.

Look at `openedx-platform/openedx/core/djangoapps/password_policy/` as a decent
reference plugin from which to copy naming patterns for plugin settings files.
The settings file containing the plugin_settings() definition will likely become:

`edx-enterprise/consent/settings/common.py`
`edx-enterprise/enterprise/settings/common.py`
`edx-enterprise/enterprise_support/settings/common.py`

# Ticketing each incremental chunk of work

The entire project is modeled as a JIRA "Initiative", while each incremental chunk of work
(representing a distinct piece of enterprise logic which should be migrated behind a hook) will be
modeled as JIRA "Epics" each with potentially multiple story tickets which may be sequenced, if
necessary.

Tickets should be stored in the current working directory as separate files following this
heirarchy:

* epics/
  * 01_feature_to_migrate/
    * EPIC.md
    * 01_<repo-name>.md
    * 01_<repo-name>.diff
    * 02_<repo-name>.md
    * 02_<repo-name>.diff
    * 03_<repo-name>.md
    * 03_<repo-name>.diff
  * 02_another_feature_to_migrate/
    * EPIC.md
    * 01_<repo-name>.md
    * 01_<repo-name>.diff
    * 02_<repo-name>.md
    * 02_<repo-name>.diff

Epic directory names should be prefixed with their sequencing order, and
describe the feature to migrate in 7 or fewer words, e.g. "07_dsc_redirects" or
"02_courseware_access_gating".

Each epic directory contains an EPIC.md file which summarizes the following:

* Purpose of existing enterprise-specific logic or settings. (1-2 sentences)
* Selected approach for migrating existing logic/settings into the edx-enterprise plugin. (1-3 sentences)
* A list of other epics which block this one.

The EPIC.md file should not be wrapped. Entire paragraphs should be on one line to allow
copy+pasting into JIRA.

## Writing a story ticket and implementation diff

Each ticket should be scoped to one PR (one repository), and should contain the
following in the body:

* Ticket name as highest level markdown header (these should be prefixed with "[<repo-name>] ").
* Clear statement about which ticket blocks this one, if any.
* One short paragraph describing the work.
* "A/C" section containing a set of Acceptance Criteria.
  * A/C section should contain a bulleted list without checkboxes since I'll be pasting this into
    JIRA which doesn't support checkboxes.
  * Don't pollute the A/C with a step to create an __init__.py file.

The ticket file should not be wrapped. Entire paragraphs should be on one line to allow
copy+pasting into JIRA.

Each ticket markdown file should be accompanied with a sibling diff file containing a complete
implementation of the ticket.

# Notes from prior brainstorming sessions

## Grades Analytics Context Enrichment

openedx-platform/lms/djangoapps/grades/events.py calls get_enterprise_event_context from
enterprise_support to enrich grade-related analytics events with enterprise metadata. We probably
want to use openedx-filter instead of django signals so that we can pass enrichment data back to the
caller.

## User Retirement

openedx-platform/openedx/core/djangoapps/user_api/accounts/views.py

User retirement pipeline queries DataSharingConsent, EnterpriseCourseEnrollment, and
EnterpriseCustomerUser to clean up enterprise-specific data.

There's already a django signal we can leverage for this: USER_RETIRE_LMS_CRITICAL.  It may just
need to be enhanced to include extra fields used by enterprise-specific retirement, including
retired_username and retired_email.

## User Account Readonly Fields

openedx-platform/openedx/core/djangoapps/user_api/accounts/views.py
openedx-platform/openedx/core/djangoapps/user_api/accounts/api.py

The update_account_settings() function is used by the account settings page & API to update
settings, but for enterprise SSO customers some of those settings should be readonly since they're
SSO managed.

We should probably create a new AccountSettingsReadOnlyFieldsRequested filter to allow plugins to
inject additional readonly fields for account settings.

Avoid using the existing AccountSettingsRenderStarted filter as it has no invocation from
openedx-platform currently, and doesn't adequately fit the use case of filtering a list of fields.

## DSC view redirect logic

openedx-platform/openedx/features/enterprise_support/api.py

Multiple courseware views/tabs are decorated with an enterprise-specific DSC redirect decorator
(data_sharing_consent_required). We should probably replace the decorator with a generic
`courseware_view_redirect` decorator, and in turn that decorator could call a new openedx-filter
named CoursewareViewRedirectURL to populate an array of redirect URLs. The new decorator can simply
run the filter and select the first element of the list to redirect, or pass if the list is empty.

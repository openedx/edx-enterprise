# Epic: Enterprise Support Module Migration

JIRA: ENT-11576

## Purpose

`openedx/features/enterprise_support/` lives inside openedx-platform but imports directly from `enterprise` and `consent` (edx-enterprise packages), keeping edx-enterprise a mandatory platform dependency even after all external callers are replaced by filter/signal hooks in epics 01–16.

## Approach

Move the entire `enterprise_support` package into edx-enterprise under `enterprise/platform_support/`. Epics 01–16 leave deferred imports in edx-enterprise plugin steps pointing to `openedx.features.enterprise_support`; this epic atomically replaces those with internal paths. Delete `openedx/features/enterprise_support/` from openedx-platform and remove its `INSTALLED_APPS` entry. Add signal handler activations (previously in `EnterpriseSupportConfig.ready()`) to `EnterpriseConfig.ready()`.

## Blocking Epics

Blocked by all epics 01–16. Every external caller of enterprise_support must be replaced by a hook before this epic ships, because this epic deletes the module from openedx-platform.

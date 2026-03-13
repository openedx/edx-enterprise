# [edx-enterprise] Copy enterprise_support into enterprise/platform_support/ and update internal imports

Blocked by: all epics 01–16 (all external openedx-platform callers of enterprise_support must be replaced before this ticket ships).

Copy the full `enterprise_support` package from openedx-platform into edx-enterprise under `enterprise/platform_support/`. Update all internal imports within the copied files to use the new `enterprise.platform_support` path instead of `openedx.features.enterprise_support`. Update all edx-enterprise plugin steps created in epics 01–16 that currently use deferred imports of `openedx.features.enterprise_support...` to import from `enterprise.platform_support...` instead. Move the signal handler activations that were in `EnterpriseSupportConfig.ready()` into `EnterpriseConfig.ready()`.

## A/C

- `enterprise/platform_support/` directory is created containing all modules from the original `openedx/features/enterprise_support/` (api.py, utils.py, context.py, signals.py, tasks.py, serializers.py, admin/, enrollments/, templates/).
- All internal `from openedx.features.enterprise_support import ...` references within the copied files are rewritten to `from enterprise.platform_support import ...`.
- All deferred `from openedx.features.enterprise_support...` imports in edx-enterprise plugin step files (epics 01–16) are updated to `from enterprise.platform_support...`.
- Signal handlers previously activated in `EnterpriseSupportConfig.ready()` are connected in `EnterpriseConfig.ready()`.
- All tests from `enterprise_support/tests/` are copied to `enterprise/tests/platform_support/` with import paths updated.
- The edx-enterprise package installs correctly without openedx-platform's enterprise_support module present.

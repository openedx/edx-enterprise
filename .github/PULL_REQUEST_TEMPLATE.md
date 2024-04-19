**Merge checklist:**
- [ ] Any new requirements are in the right place (do **not** manually modify the `requirements/*.txt` files)
    - `base.in` if needed in production but edx-platform doesn't install it
    - `test-master.in` if edx-platform pins it, with a matching version
    - `make upgrade && make requirements` have been run to regenerate requirements
- [ ] `make static` has been run to update webpack bundling if any static content was updated
- [ ] `./manage.py makemigrations` has been run
    - Checkout the [Database Migration](https://openedx.atlassian.net/wiki/spaces/AC/pages/23003228/Everything+About+Database+Migrations) Confluence page for helpful tips on creating migrations.
    - *Note*: This **must** be run if you modified any models.
      - It may or may not make a migration depending on exactly what you modified, but it should still be run.
    - This should be run from either a venv with all the lms/edx-enterprise requirements installed or if you checked out edx-enterprise into the src directory used by lms, you can run this command through an lms shell.
        - It would be `./manage.py lms makemigrations` in the shell.
- [ ] [Version](https://github.com/openedx/edx-enterprise/blob/master/enterprise/__init__.py) bumped
- [ ] [Changelog](https://github.com/openedx/edx-enterprise/blob/master/CHANGELOG.rst) record added
- [ ] Translations updated (see docs/internationalization.rst but also this isn't blocking for merge atm)

**Post merge:**
- [ ] Tag pushed and a new [version](https://github.com/openedx/edx-enterprise/releases) released
    - *Note*: Assets will be added automatically. You just need to provide a tag (should match your version number) and title and description.
- [ ] After versioned build finishes in [GitHub Actions](https://github.com/openedx/edx-enterprise/actions), verify version has been pushed to [PyPI](https://pypi.org/project/edx-enterprise/)
    - Each step in the release build has a condition flag that checks if the rest of the steps are done and if so will deploy to PyPi.
    (so basically once your build finishes, after maybe a minute you should see the new version in PyPi automatically (on refresh))
- [ ] PR created in [edx-platform](https://github.com/openedx/edx-platform) to upgrade dependencies (including edx-enterprise)
    - Trigger the '[Upgrade one Python dependency](https://github.com/openedx/edx-platform/actions/workflows/upgrade-one-python-dependency.yml)' action against master in edx-platform with new version number to generate version bump PR
    - This **must** be done after the version is visible in PyPi as `make upgrade` in edx-platform will look for the latest version in PyPi.
    - Note: the edx-enterprise constraint in edx-platform **must** also be bumped to the latest version in PyPi.

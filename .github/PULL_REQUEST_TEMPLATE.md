**Merge checklist:**
- [ ] Any new requirements are in the right place (do **not** manually modify the `requirements/*.txt` files)
    - `base.in` if needed in production but edx-platform doesn't install it
    - `test-master.in` if edx-platform pins it, with a matching version
    - `make upgrade && make requirements` have been run to regenerate requirements
- [ ] `make static` has been run to update webpack bundling if any static content was updated
- [ ] [Version](https://github.com/edx/edx-enterprise/blob/master/enterprise/__init__.py) bumped
- [ ] [Changelog](https://github.com/edx/edx-enterprise/blob/master/CHANGELOG.rst) record added
- [ ] Translations updated (see docs/internationalization.rst but also this isn't blocking for merge atm)

**Post merge:**
- [ ] Tag pushed and a new [version](https://github.com/edx/edx-enterprise/releases) released
    - *Note*: Assets will be added automatically. You just need to provide a tag (should match your version number) and title and description.
- [ ] After versioned build finishes in [Travis](https://travis-ci.org/github/edx/edx-enterprise), verify version has been pushed to [PyPI](https://pypi.org/project/edx-enterprise/)
    - Each step in the release build has a condition flag that checks if the rest of the steps are done and if so will deploy to PyPi.
    (so basically once your build finishes, after maybe a minute you should see the new version in PyPi automatically (on refresh))
- [ ] PR created in [edx-platform](https://github.com/edx/edx-platform) to upgrade dependencies (including edx-enterprise)
    - This **must** be done after the version is visible in PyPi as a `make upgrade` in edx-platform will look for the latest version in PyPi.

**Merge checklist:**
- [ ] Any new requirements are in the right place (do **not** manually modify the `requirements/*.txt` files)
    - `base.in` if needed in production but edx-platform doesn't install it
    - `test-master.in` if edx-platform pins it, with a matching version
    - `make upgrade && make requirements` have been run to regenerate requirements
- [ ] `make static` has been run to update webpack bundling if any static content was updated
- [ ] [Version](https://github.com/edx/edx-enterprise/blob/master/enterprise/__init__.py) bumped
- [ ] [Changelog](https://github.com/edx/edx-enterprise/blob/master/CHANGELOG.rst) record added
- [ ] Translations updated

**Post merge:**
- [ ] Tag pushed and a new [version](https://github.com/edx/edx-enterprise/releases) released
- [ ] Version pushed to [PyPI](https://pypi.org/project/edx-enterprise/)
- [ ] PR created in [edx-platform](https://github.com/edx/edx-platform) to upgrade dependencies (including edx-enterprise)

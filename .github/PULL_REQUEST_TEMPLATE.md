**Description:** Describe in a couple of sentence what this PR adds

**JIRA:** Link to JIRA ticket

**Dependencies:** dependencies on other outstanding PRs, issues, etc. 

**Merge deadline:** List merge deadline (if any)

**Installation instructions:** List any non-trivial installation 
instructions.

**Testing instructions:**

1. Open page A
2. Do thing B
3. Expect C to happen
4. If D happend instead - check failed.

**Merge checklist:**

- [ ] Check that the versions of the requirements in the `platform-master.in` file match edx-platform.
- [ ] New requirements are in the right place (`base.in` if only used in enterprise; in the correct `platform-****.in` files if they're hosted in edx-platform)
- [ ] Regenerate requirements with `make upgrade && make requirements` (and make sure to fix any errors).
  **DO NOT** just add dependencies to `requirements/*.txt` files.
- [ ] Called `make static` for webpack bundling if any static content was updated.
- [ ] All reviewers approved
- [ ] CI build is green
- [ ] Version bumped
- [ ] Changelog record added
- [ ] Documentation updated (not only docstrings)
- [ ] Commits are (reasonably) squashed
- [ ] Translations are updated
- [ ] PR author is listed in AUTHORS

**Post merge:**
- [ ] Create a tag
- [ ] Check new version is pushed to PyPi after tag-triggered build is finished.
- [ ] Delete working branch (if not needed anymore)
- [ ] edx-platform PR (be sure to include edx-platform requirements upgrades that were present in this PR)

**Author concerns:** List any concerns about this PR - inelegant 
solutions, hacks, quick-and-dirty implementations, concerns about 
migrations, etc.

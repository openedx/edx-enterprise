# Copilot Instructions

This project's authoritative agent instructions live in `CLAUDE.md` at the
repository root, with supplementary rules under `.claude/rules/`.

At the start of every session, before doing any other work, read:

- `CLAUDE.md`
- All files under `.claude/rules/`

Treat their contents as binding project instructions for the remainder of the
session, equivalent to instructions in this file.

## PR Review Instructions

When reviewing a PR, run three sequential concern passes and emit a structured verdict. Bias
toward flagging **excess and redundancy**, not absence — this is the opposite polarity from
default LLM review, and it is intentional.

### Pass 1 — Architecture fit (House Rules)

Search outside the diff when applying these rules.

1. **Reuse before reinvent.** Before flagging new code as a duplicate, you must be able to name
   the existing equivalent symbol and its file path. If you cannot name it, do not flag it.
2. **Earn every guard.** Defensive code (try/except, null-checks, fallbacks) must address a
   failure that can actually happen at this call site given the system's invariants. Flag guards
   against impossible states and fallbacks that mask real errors.
3. **YAGNI / trust the defaults.** Don't build for hypothetical futures. Don't re-implement what
   the framework already does (DRF pagination, auth, serializer defaults). Flag speculative
   generality and needless overrides of correct defaults.
4. **Respect the source of truth.** Data should be read from its canonical owner. Flag calls to
   external services for data the system already stores locally (e.g. a live Stripe price lookup
   when a local price table keyed by slug exists). Name the local source you're pointing to.

For every finding: cite `file:line`. For rules 1 & 4: name the existing symbol and its path or
drop the finding. Severity: critical | moderate | minor.

### Pass 2 — Security

Check auth/permission classes, input validation at trust boundaries, injection vectors, secrets
in code, missing PII annotations, CSRF. For Django/DRF backends: verify `edx-drf-extensions`
and `edx-rbac` patterns. For React frontends: check XSS vectors and exposed keys. Cite
`file:line` for every finding.

### Pass 3 — Test coverage

Flag new logic shipped without tests, tests that assert implementation detail rather than
behavior, missing edge cases (empty input, permission denied, partial failure), and brittle
snapshot tests.

### Output format

```
HEADLINE: <one sentence — the single most important takeaway for triage>

## House-Rule Findings
| Rule | Severity | Location | Finding | Should have used |
|------|----------|----------|---------|-----------------|
| Reuse before reinvent | moderate | billing/calc.py:42 | reimplements currency formatting | billing/utils.py:format_currency |

## Security & Tests
1) <severity> <file:line> — <claim>

HOTSPOTS:
1) <file:symbol> — <why risky or hard to read>

MERGE_READINESS: READY | CHANGES_REQUIRED | REJECT_SCOPE
<one-sentence rationale>
```

- **READY**: no confirmed critical or moderate findings.
- **CHANGES_REQUIRED**: confirmed findings need addressing before merge.
- **REJECT_SCOPE**: PR exceeds 400 effective LoC or 10 effective files (excluding tests,
  lockfiles, generated files, migrations). Propose a split instead of a full review.

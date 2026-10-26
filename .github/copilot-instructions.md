# Copilot Instructions

This project's authoritative agent instructions live in `CLAUDE.md` at the
repository root, with supplementary rules under `.claude/rules/`.

At the start of every session, before doing any other work, read:

- `CLAUDE.md`
- All files under `.claude/rules/`

Treat their contents as binding project instructions for the remainder of the
session, equivalent to instructions in this file.

## PR Review Instructions

When reviewing a PR, focus on the areas below.

### Code correctness and performance

1. Flag incorrect business logic.
2. Flag areas that are potentially inefficient or unperformant.

### Excess and redundancy

Bias toward flagging **excess and redundancy**.

1. **Reuse before reinvent.** Flag code that duplicates existing functionality - identify the existing equivalent symbol.
2. **Earn every guard.** Defensive code (try/except, null-checks, fallbacks) must address a
   failure that can actually happen at this call site given the system's invariants.
3. **Don't swallow exceptions.** If you catch an exception, re-raise it or convert it to a more actionable error; avoid catch-and-log-only (or catch-and-ignore) handling.
4. **YAGNI / trust the defaults.** Don't build for hypothetical futures. Don't re-implement what
   the framework already does (DRF pagination, auth, serializer defaults). Flag speculative
   generality and needless overrides of correct defaults.
5. **Respect the source of truth.** Data should be read from its canonical owner. Flag calls to
   external services for data the system already stores locally (e.g. a live Stripe price lookup
   when a local price table keyed by slug exists). Name the local source you're pointing to.

### Security

Check auth/permission classes, input validation at trust boundaries, injection vectors, secrets
in code, missing PII annotations, CSRF. For Django/DRF backends: verify `edx-drf-extensions`
and `edx-rbac` patterns. For React frontends: check XSS vectors and exposed keys. Cite
`file:line` for every finding.

### Test coverage

Flag new logic shipped without tests, tests that assert implementation detail rather than
behavior, missing edge cases that can actually happen, and brittle snapshot tests.

### Output format

Briefly highlight any critical or high severity issues.

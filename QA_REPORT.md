# MKDSS Compliance Management System — Notification/Publication Fix QA

## QA status
CANDIDATE — not final. Full Django runtime QA must still be executed in the target Windows environment.

## Fixes implemented
1. Existing initial request approval notifications are retargeted to the live Approval Queue when the request is decided.
2. Existing document final-approval notifications are retargeted to the live Approval Queue when the version is decided.
3. Stale approval URLs remain protected at the view layer and redirect to the Approval Queue instead of raising a raw error.
4. Compliance's document-approved notification opens the exact document detail page.
5. Published Documents are ordered by latest publication timestamp, with primary-key tie-breaker.
6. Published Documents displays Published Date.
7. Notification regression tests include the required model imports and lifecycle checks.

## Static QA performed
- Python `compileall`: PASS
- Source assertions for request notification retargeting: PASS
- Source assertions for document notification retargeting: PASS
- Source assertion for stale request/document guards: PASS
- Source assertion for latest publication ordering: PASS
- Source assertion for Published Date column: PASS
- Test source import validation: PASS
- Static test count: 43

## Runtime QA
The full Django test suite could not be executed in this build environment because Django is not installed and package installation/network access is unavailable here.

Therefore this package is intentionally NOT marked final. Run in the target Windows environment:

    venv\\Scripts\\python.exe manage.py check
    venv\\Scripts\\python.exe manage.py migrate
    venv\\Scripts\\python.exe manage.py test

Acceptance gate:
- `check` must pass.
- `migrate` must report no unapplied migrations for this change.
- All tests must finish with `OK`.
- Any failure must be fixed and the complete suite rerun before this package is considered final.

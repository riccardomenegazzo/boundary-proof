# Contributing

Run `python3 -m unittest discover -s tests -v`, `node --check dist/app.js` and `node tests/dashboard.test.cjs`. Docker runner changes must pass both integration jobs.

Explain the customer decision improved and the observations actually measured. Keep Python and browser decision semantics consistent. Never count timeout, API failure, missing observations or cleanup failure as a successful boundary verification. Do not show fabricated evidence as measured results.

New backends require explicit runtime capability checks and a documented threat model. Do not add privileged containers, real credential mounts or host socket access to default scenarios. Preserve the host/controller and model credential boundaries. Test report validation, local API authorization and cleanup behavior for relevant changes.

The dashboard source is `dist/`; the wheel build copies those assets into package data. Do not maintain a second authored dashboard tree.

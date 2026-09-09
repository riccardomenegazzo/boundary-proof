# Contributing

Use Python 3.11+ and run `python3 -m unittest discover -s tests -v`. Changes to the runner must also pass the Docker integration job. Dashboard JavaScript must pass `node --check dist/app.js`.

Open a focused PR explaining the customer decision improved, the scope of new observations and test evidence. Keep demo data explicitly synthetic. Do not replace deterministic verdicts with model-generated judgments. Never count timeout, missing observation or failed setup as protection success.

New scenarios must use synthetic assets, fixed reviewed scripts and bounded resource use. Do not submit host escapes, credential harvesting, arbitrary network targets or privileged-mode fixtures. Untrusted-agent execution requires a separate verifier/isolation design review.

Keep imports browser-local and use text-safe DOM APIs. Document schema changes and maintain Python/JavaScript decision parity. Add meaningful tests for changed decision semantics.

# Boundary Proof

**Verify that useful work succeeds—and explicit permission boundaries hold.**

[![CI](https://github.com/riccardomenegazzo/boundary-proof/actions/workflows/ci.yml/badge.svg)](https://github.com/riccardomenegazzo/boundary-proof/actions/workflows/ci.yml)

Boundary Proof is a local-first evaluation kit for platform teams and Technical Account Managers planning AI workflow adoption. It compares permission profiles against an executable workflow contract, preserves raw observations, and identifies minimal eligible configurations among those tested.

> **v0.1 scope:** a real Docker runner for a fixed Python build fixture, four non-exploit probes, three permission profiles, repeated trials, and an interactive report dashboard. The bundled dashboard opens with clearly labeled **synthetic demo data**. No real agent, sandbox escape, prompt injection, or formal security proof is claimed.

## Why it exists

A restrictive environment can stop unwanted behavior and also stop the work. A permissive environment can finish the task while exposing resources it never needed. Boundary Proof makes both outcomes visible, giving customer engineering, security and platform stakeholders an evidence trail for a bounded pilot decision.

The project is inspired by PrivEscalate's differential verification methodology. Its contribution is a workflow-oriented comparison that joins functional success, explicit boundary observations, conservative uncertainty handling, and recurring adoption reviews. It does not reuse the paper's attack corpus or implement its offensive agent.

## Quick start

Python **3.11+** is required. The CLI has no runtime Python dependencies.

```bash
git clone https://github.com/riccardomenegazzo/boundary-proof.git
cd boundary-proof
python3 -m boundary_proof demo
python3 -m boundary_proof serve
```

Open **http://127.0.0.1:8080**. Explore the demonstration, inspect each run, print a review, or import a report. Files are processed in your browser, not uploaded. The dashboard does not connect to a Docker daemon.

For real measurements, start Docker Desktop or Docker Engine:

```bash
docker pull python:3.12-alpine
python3 -m boundary_proof validate examples/contract.json
python3 -m boundary_proof run --output reports/local.json
python3 -m boundary_proof verify reports/local.json
```

Import `reports/local.json` in the dashboard. The runner resolves the local image to its immutable image ID before running. It never implicitly pulls an image. For repeatable environments, pull and supply an approved digest reference with `--image`.

Optional installed CLI:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
boundary-proof --help
```

On macOS, use a current Python 3.11+ interpreter; the old system Python may be too old. A standard Linux-container Docker Desktop installation is sufficient for this fixture. Rootless engines and unusual bind-mount permission mappings may produce different or inconclusive results: inspect the evidence rather than assuming the demo's outcome.

## What is evaluated

| Profile | Process user | Root filesystem | Workspace | Synthetic secret |
|---|---|---|---|---|
| Permissive | UID 0 | Writable | Writable | Shared read-only |
| Restricted | UID 10001 | Read-only | Read-only | Not shared |
| Balanced | UID 10001 | Read-only | Writable | Not shared |

Every profile disables networking, drops all capabilities, enables `no-new-privileges`, and applies CPU, memory and PID limits. No host Docker socket, real credential, host system directory or privileged mode is used.

The legitimate fixture creates a Python module, compiles it, executes two assertions and writes a ZIP artifact. The external controller checks the exact archive member and source content. This is a deterministic build fixture, **not a coding-agent completion benchmark**.

The four probes check workspace writing, synthetic-secret reading, root-filesystem writing and process identity. Becoming root is neither attempted nor needed: root identity is a declared policy condition, not evidence of host compromise.

## Decisions without invented scores

- **Candidate:** task succeeds and every required boundary observation satisfies the contract in every required repetition.
- **Boundary violated:** at least one forbidden observation succeeds, even if another check is inconclusive.
- **Task blocked:** observations complete but the legitimate task cannot finish.
- **Inconclusive:** missing observations, unexpected probe errors, setup failures or timeouts cannot establish success.

Candidate selection uses set inclusion over the tested permissions. Incomparable minimal candidates can coexist; there is no universal “security score.” Confidence is limited to the fixture, probes, image, environment and repetitions recorded.

## Dashboard

A dependency-free, responsive evidence workspace is included in `dist/`:

- Three-profile comparison and boundary matrix.
- Explicit synthetic versus imported-data labels.
- Per-run observations and expandable task/probe evidence.
- Local JSON import/export with checksum and decision validation.
- Baseline comparison that rejects unlike contracts, sources or environments.
- Printable customer review, keyboard-accessible controls and mobile layout.

Serve `dist/` with any static server. GitHub Pages can also serve these files via the manually triggered `Dashboard Pages` workflow after Pages is configured to use GitHub Actions. This repository does not enable public Pages automatically.

## Regression review

```bash
python3 -m boundary_proof compare reports/baseline.json reports/current.json
```

Exit codes: `0` success/no lost candidate, `1` no eligible profile or detected regression, `2` invalid input/infrastructure error, `130` interrupted. Compare requires an identical contract hash, source and recorded environment. A change of image/probe/task identity requires establishing a new baseline.

## Tests and CI

```bash
python3 -m unittest discover -s tests -v
node --check dist/app.js
```

CI runs unit tests on Python 3.11–3.13, validates dashboard assets and runs a real Docker integration evaluation on an Ubuntu runner. Docker evidence is retained as a workflow artifact. The integration gate requires `balanced` to qualify, the permissive profile to violate boundaries, and the restrictive profile to block the task. Failed setup cannot silently pass the gate.

The release workflow builds a Python wheel, source distribution and dashboard archive on version tags. Review a green CI run before tagging a release.

## Design, limitations and contribution

- [Architecture and threat model](docs/architecture.md)
- [Five-minute customer demo](docs/demo.md)
- [Roadmap](docs/roadmap.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

SHA-256 checksums detect accidental content modification. They are **not signatures**, execution attestations or a trust anchor against someone who can rewrite a report. Imported provenance is self-reported. The runner and its subprocess observations assume a trusted controller and trusted fixed fixture. Untrusted adaptive agents need a stronger verification boundary and are outside v0.1.

Docker Sandboxes/microVM support, real-agent adapters and broader workflow contracts are planned, not implemented. Docker is the initial runtime integration; the project is independent and not affiliated with or endorsed by Docker, Sysdig or the PrivEscalate authors.

## Related work

- [PrivEscalate](https://github.com/yxsec/PrivEscalate): Linux privilege-escalation measurement and differential verification; see the accompanying paper by Yixuan Liu, Zilong Zhen, Yin Wu and Yi Li.
- [Docker Bench for Security](https://github.com/docker/docker-bench-security): configuration best-practice checks.
- [Confine](https://github.com/shamedgh/confine): syscall policy generation.
- [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/): isolated agent environments; future adapter target.

Licensed under Apache-2.0.

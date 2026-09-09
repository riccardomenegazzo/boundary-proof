# Boundary Proof

**Run your repository under different permissions. Verify the work independently. Inspect the evidence.**

[![CI](https://github.com/riccardomenegazzo/boundary-proof/actions/workflows/ci.yml/badge.svg)](https://github.com/riccardomenegazzo/boundary-proof/actions/workflows/ci.yml)

Boundary Proof is an open-source evaluation application for platform teams and Technical Account Managers managing AI workflow adoption. It executes committed repositories in Docker, compares configurable permission profiles, runs acceptance scripts in a separate verifier, and provides a local dashboard for starting, cancelling and reviewing evaluations.

**The application starts empty. It never fills the dashboard with fabricated results.**

## Start a real evaluation

Requirements: Python 3.11+, Git, and a running Docker Desktop or Docker Engine with Linux containers.

```bash
git clone https://github.com/riccardomenegazzo/boundary-proof.git
cd boundary-proof
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
docker pull python:3.12-alpine
boundary-proof doctor
boundary-proof serve --repo . --contract boundary.json
```

Open the **complete session URL** printed in the terminal. Click **Run evaluation**. The included contract evaluates Boundary Proof's actual source: compilation, source packaging and independent acceptance checks. Observe progress, select a recorded evaluation and inspect its commands, verification output and artifact hashes.

For CLI-only use:

```bash
boundary-proof run --repo . --contract boundary.json --output reports/result.json
boundary-proof verify reports/result.json
boundary-proof compare reports/baseline.json reports/result.json
```

The wheel includes the dashboard. Running `boundary-proof serve` after installation does not require a frontend build or Node. The server binds to loopback and accepts only the session token it generated. Reports persist under `~/.boundary-proof/reports` by default; override with `--state`.

## Evaluate your own repository

```bash
cd /path/to/your/repository
boundary-proof init --name 'Platform adoption evaluation'
```

Edit `boundary.json`: choose a locally available image, workload commands, permission profiles and acceptance scripts. Add your acceptance script to the repository and commit all tracked changes. Then start `boundary-proof serve --repo . --contract boundary.json`.

The runner evaluates **committed HEAD only**, ignoring untracked files and rejecting dirty tracked files, submodules, symlinks and common credential file paths. This makes source identity explicit. It does not replace a secret scanner: review the selected repository before execution or use with a remote model.

The selected image must contain **Python 3.11.8+** for seeding/probes and every dependency your workload requires. Network access inside the containers is disabled; install dependencies in an approved image beforehand. An existing Node, Go or other application can be evaluated using an image that also contains Python for the controller's probes.

### Contract example

```json
{
  "schema_version": "2.0",
  "name": "Service build",
  "owner": "Platform Engineering",
  "objective": "Build the package and satisfy independent acceptance checks",
  "workflow": "repository",
  "image": "my-approved-build-image:latest",
  "repeats": 3,
  "timeout_seconds": 120,
  "required_checks": ["workspace_write", "secret_read", "rootfs_write", "root_identity"],
  "steps": [["python", "build.py"]],
  "verify": [["python", "/reference/boundary_verify.py"]],
  "artifacts": ["build/package.zip"],
  "profiles": {
    "limited": {
      "user": "10001:10001",
      "read_only": true,
      "secret_shared": false,
      "workspace_writable": true
    }
  }
}
```

`steps` are argument arrays executed inside the workspace container. They are never executed by a host shell. The workload sees `/workspace` and an immutable `/reference` snapshot.

`verify` scripts are loaded from `/reference`, executed with Python isolated mode, and should inspect `/workspace`. The worker is removed before verification. The verifier receives both volumes read-only and a writable temporary directory; it cannot quietly rewrite the output to make a test pass. See [the repository's acceptance script](tests/acceptance.py).

Artifact entries must be relative file paths. The verifier records SHA-256 and size, rejects symlinks, and caps each file at 50 MB. Acceptance scripts remain responsible for semantic correctness.

## Run a real tool-calling agent

Add an optional `agent` section to a repository contract:

```json
"agent": {
  "model": "YOUR_PROVIDER_MODEL_ID",
  "instruction": "Inspect the repository and complete the requested change. Preserve the acceptance tests and produce the required build artifact.",
  "max_turns": 12
}
```

Set `BOUNDARY_PROOF_API_KEY` in the **controller's environment**. Optionally set `BOUNDARY_PROOF_API_BASE` to a Chat Completions compatible `/v1` endpoint. It defaults to `https://api.openai.com/v1`; local providers may use a loopback HTTP endpoint without a key.

Workload preparation steps run first. The agent then uses a `container_command` tool, with each command executed inside the existing restricted worker. The API key never enters the container. Command observations are sent to the configured provider and can include repository contents: use a provider approved for that source. Turns, usage and command traces appear in the report. Timeout, invalid tool calls, API failure and exhausted budgets are inconclusive.

**The agent's final message never determines the verdict.** Independent acceptance checks run afterward. The protocol adapter has automated tests; live model quality depends on the selected provider/model and must be measured using your configured credentials. There is no bundled fake model presented as a real agent evaluation.

## What the dashboard does

| Local workspace | Hosted/static viewer |
|---|---|
| Start/cancel real Docker evaluations | Import measured JSON reports |
| Edit and validate contracts | Validate report consistency and checksum |
| Monitor progress and failures | Compare permission profiles |
| Select persistent evaluation history | Inspect workflow, agent and verifier traces |
| Inspect measured results | Compare baselines and print reviews |

Imported reports stay in the browser. A hosted viewer deliberately cannot control your Docker daemon. To execute evaluations, open the session URL from the local CLI. The same dashboard assets are used in both modes.

## Decision semantics

- **Candidate:** every required repetition completes useful work and satisfies all four checked conditions.
- **Boundary violated:** a forbidden observation succeeds.
- **Task blocked:** observations finish but the workload fails.
- **Inconclusive:** missing observations, infrastructure errors, failed cleanup, cancellation or unknown execution results.

Candidate selection compares permission sets, retaining minimal eligible profiles and allowing incomparable candidates. It does not invent a numerical security score. Baseline comparisons require the same contract, source type and recorded runtime environment; repository commits may differ so code regressions can be detected.

The probes cover a writable workspace, one synthetic secret, one root-filesystem canary and non-root identity. UID 0 is a contract condition, not evidence of host escape. Kernel attacks, network egress policy and Docker socket escape are not assessed by these probes.

## Isolation and limits

Every worker/verifier has disabled networking, dropped capabilities, no-new-privileges and CPU/memory/PID limits. Workspaces use disposable named volumes, not the customer's live repository. No host runtime socket or genuine credential is mounted. Resources carry an evaluation label and are removed on completion/cancellation; forced termination can still require manual cleanup of that run's named resources.

Docker Engine containers are not a containment guarantee against kernel exploitation. Use a dedicated disposable VM for untrusted agent experimentation. The verifier is separate from the worker, but executes customer acceptance code and may import generated code; this is not a formally adversarially robust proof system. SHA-256 checksums detect content changes, not forged provenance.

Docker Sandboxes/microVM-native integration is **not implemented**; no current result is labeled as such. Boundary Proof works with Docker Engine, including Docker Desktop's Engine.

## Validation and packaging

```bash
python3 -m unittest discover -s tests -v
node --check dist/app.js
node tests/dashboard.test.cjs
python3 -m pip wheel . --no-deps --wheel-dir /tmp/boundary-proof-wheel
```

CI covers Python 3.11–3.13, the legacy fixture, and the real repository evaluation with independent checks. Reports are saved as workflow artifacts. The release workflow builds an installable wheel, source distribution and standalone dashboard archive on version tags.

Exit codes: `0` success/no lost candidate; `1` no qualifying profile or detected regression; `2` input/infrastructure error; `130` interruption.

## Project background

Inspired by the differential verification approach in [PrivEscalate](https://github.com/yxsec/PrivEscalate), Boundary Proof focuses on a customer adoption decision: which tested permissions preserve useful work and satisfy explicit observed boundaries? It does not reuse the paper's exploit corpus or implement its offensive escalation agent.

Related work: [Docker Bench for Security](https://github.com/docker/docker-bench-security), [Confine](https://github.com/shamedgh/confine), [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/).

[Architecture](docs/architecture.md) · [Operating guide](docs/operations.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

Independent project, not affiliated with or endorsed by Docker, Sysdig or the paper's authors. Apache-2.0.

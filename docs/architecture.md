# Architecture and threat model

## Data flow

1. A local CLI validates a versioned JSON workflow contract.
2. The host controller resolves the existing image to an immutable image ID.
3. Each trial receives a fresh container and temporary synthetic workspace.
4. Fixed probes record four observable conditions. Their exit code vocabulary is controller-defined; arbitrary errors are inconclusive.
5. The deterministic task compiles/tests/packages a tiny Python fixture.
6. The controller checks the produced artifact, removes its named container, and stores evidence.
7. A pure evaluator assigns verdicts and the minimal eligible profile set.
8. The static dashboard reads portable JSON entirely in the browser.

The browser cannot launch containers or change policy. The CLI never accepts arbitrary shell commands, mounts or Docker flags from a contract. Host subprocesses use argument arrays and never `shell=True`.

## Trust boundary

The host, Docker daemon, CLI, local image and fixed scripts are trusted for this release. Containers exercise known synthetic conditions; they are not a safe containment environment for unknown kernel exploits or malicious agent code. Privileged execution, host runtime access and genuine secrets are unnecessary and absent.

The controller owns evaluation, but individual probe observations originate in a container process. An adaptive attacker could forge exit codes, race filesystem checks or interfere with probes. Therefore v0.1 is **not an adversarially robust verifier**. A future untrusted-agent adapter must isolate probe execution and observation, restrict artifact handling, and use an outer disposable VM or appropriate sandbox boundary.

An ordinary container is not claimed to contain kernel exploits. Docker Sandboxes uses a different isolation architecture and is not implemented by wrapping this runner or relabeling its results.

## Contract semantics

All four checks are mandatory in v1.0. `root_identity` states that the process must be non-root; it never implies a root process escaped the container. `secret_read` protects a synthetic string only. `rootfs_write` attempts one canary path, not every filesystem location. `workspace_write` is a functional capability condition.

A denied operation at the tested path establishes that bounded observation only. ENOENT is a blocked outcome for an unshared synthetic resource. Missing dependencies, Docker exec failures, timeouts and unexplained errors are inconclusive. A known forbidden success takes precedence over uncertainty elsewhere.

Only the audited `python-build` workflow is accepted. The `owner` and `objective` fields communicate intent; arbitrary prose is not converted to executable policy.

## Comparability

The report records image ID, Docker server version, task/probe hashes, network mode and contract hash. Baseline comparison demands equality of the recorded environment. This is conservative but not a complete environment fingerprint: kernel, virtualization, storage, hardware and daemon policy are not exhaustively captured. No timing or causal-performance claims are made from these reports. Recorded durations are diagnostics only.

## Evidence integrity

Reports include a canonical JSON SHA-256 checksum. Python and browser validators also recompute verdicts, repetitions, summaries and minimal candidate selection. Anyone able to edit the report can recompute a checksum; authenticity requires a separately trusted signature/attestation, intentionally deferred.

## Failure handling

All real trials attempt container removal in `finally`. Cleanup failures appear explicitly in the run. If the process is forcibly killed, inspect containers named `boundary-proof-*` and remove only those belonging to the interrupted evaluation. Temporary workspace mounts are created by the runner. No global Docker prune is used.

The local dashboard server binds to loopback and serves only the selected static directory. The hosted dashboard never receives imported reports. Raw imported strings are inserted as text nodes, not HTML.

# Architecture

The repository evaluator snapshots committed Git HEAD and records its digest. A seed container restores the archive into two disposable volumes: writable candidate workspace and original reference. Per-profile workers execute commands and optional agent tools. The worker is removed before an independent verifier mounts both volumes read-only and runs acceptance scripts from `/reference` in Python isolated mode. The controller records observations, artifact hashes, command traces, resource cleanup and a permission-set decision.

The local service binds to loopback, validates Host and Origin, requires a random session token for APIs, and fixes the repository path at startup. Only one evaluation runs at a time. A background thread records progress and persists the final/partial report atomically. Reports survive service restarts. The UI can launch, cancel, inspect history and edit validated contracts in local mode; a static hosted viewer supports local import and report analysis.

The optional model adapter lives on the controller. Credentials remain there. Only a container-command function is exposed to the model; its tool calls cannot supply Docker options or choose a host subprocess. Transcript observations travel to the operator-configured provider. The model is not a verifier.

## Explicit limits

This is an operational, bounded evaluation tool, not formal proof of isolation. Docker Engine shares a kernel with its host/VM. Use a disposable outer VM when executing untrusted agents. The separate verifier can execute generated application code through customer acceptance scripts, so it is not a trusted hardware oracle immune to all adversarial interference. Checks cover the named synthetic observations only.

Workspace mounts are Docker volumes rather than live source mounts. The only bind-mounted probe asset is a synthetic constant. The image is resolved to an immutable local ID; networking is disabled in every container. Jobs use CPU, memory, PID, time, transcript and artifact limits, but these do not replace host-level quota enforcement.

Baselines require the same contract and recorded runtime fingerprint. Commits may differ. Hashes give content identity, not publisher authenticity. Different reports cannot establish causal performance improvements; durations are diagnostic measurements only.

Legacy schema 1.0 reports remain readable. Schema 2.0 adds configurable profiles, repository identity, workload/verification traces, artifact metadata and optional model execution. The old synthetic fixture is a test resource, not dashboard content.

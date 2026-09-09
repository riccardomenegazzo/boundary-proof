# Operating guide

## First evaluation

1. Install the wheel or install from the checkout with `python3 -m pip install .`.
2. Start Docker and explicitly pull the chosen build image.
3. Run `boundary-proof doctor`.
4. Commit the selected repository's tracked files. Review the source for secrets.
5. Set workload steps and immutable acceptance scripts in `boundary.json`.
6. Start `boundary-proof serve --repo . --contract boundary.json` and open its full session URL.
7. Review/edit the contract, validate it and run the evaluation.
8. Inspect every profile and export or print the evidence for a pilot review.

A contract in the browser is evaluated against the server's explicitly selected repository only. It cannot change the host path or append arbitrary Docker options.

## Acceptance scripts

Python runs with `-I`, so the workspace cannot inject `sitecustomize` into the verifier at startup. Your acceptance script can deliberately import application code from `/workspace` by adding that path to `sys.path`. Treat that imported code as untrusted and keep the verifier inside an appropriate outer boundary. Acceptance scripts must write temporary data under `/tmp`, not either read-only volume. They must exit nonzero on failure.

## Agent configuration

The host controller calls a Chat Completions compatible endpoint. Set `BOUNDARY_PROOF_API_KEY` securely in the launching environment; never put it in a contract. `BOUNDARY_PROOF_API_BASE` is configured by the operator, not an editable browser field. Remote endpoints require HTTPS and redirects are rejected. Command output may be sent to the provider. No model runs occur unless the contract explicitly contains an `agent` section.

Set preparation steps to install/build prerequisites already available offline. Agent tools execute only in the worker, whose network is disabled. Select a turn budget and command timeout. The final decision still requires independent acceptance checks and boundary observations.

## Cancellation and recovery

Cancel in the dashboard or stop the CLI with Ctrl-C. Cleanup removes only containers and volumes allocated by that evaluation. Cancellation preserves partial reports in local workspace mode. A hard process/host crash can leave labeled resources; inspect `org.boundary-proof.run` labels and remove only the affected evaluation's resources. Do not use global prune to clean up a single evaluation.

## Data handling

Local workspace reports live in the selected `--state` directory. Protect that directory as you would repository build logs. Imported files in the static viewer are processed in memory and not sent to a server. A report checksum is not a digital signature. Only the local session token permits API access; restarting the service creates a new token.

## Troubleshooting

- Missing image: explicitly `docker pull` the approved image/digest.
- Missing Python/dependencies: build an approved image containing Python 3.11.8+ and the workload tools.
- Dirty repository: commit tracked changes; untracked files are intentionally excluded.
- Inconclusive: expand setup errors, agent traces, command evidence and cleanup status.
- Read-only verification error: acceptance code should use `/tmp` for scratch writes.
- Empty dashboard: connect through the local session URL or import a report; empty is the intended first state.

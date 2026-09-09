# Security policy

Boundary Proof evaluates user-selected repository workflows. Its Docker backend is not a containment guarantee against kernel exploits. Use a dedicated disposable VM for untrusted agents. The local API requires a session token, verifies Host/Origin, binds to loopback and evaluates only the repository selected at launch. Do not expose it through a public reverse proxy.

Model-provider credentials remain on the host controller; command outputs may be sent to the configured provider. Never commit credentials or use confidential source without the appropriate provider approval. No genuine secret is needed for boundary probes.

Checksums are not signatures. Independent acceptance execution limits worker interference but does not provide a formally adversarially robust oracle when acceptance scripts import generated code. Reports establish only the recorded observations.

Use GitHub private vulnerability reporting if available. Otherwise request a private channel without including exploit details or sensitive data in a public issue. Supported scope: current main and latest 0.2 release.

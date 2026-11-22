# Security Policy

## Reporting a vulnerability

Report privately. Use GitHub private vulnerability reporting on this repository (Security tab, "Report a vulnerability"). Do not open a public issue for a security problem.

Contact line, used only if private reporting is unavailable: hello@dipenpatel.dev

Please include the steps to reproduce, the Tollgate version (the `VERSION` file) and your OS. Use synthetic data only; never send real PHI or credentials.

## Supported versions

Only the latest release on `main` gets fixes.

## Scope

Tollgate is a set of guardrails for a cooperative AI model. It is not a sandbox. Its hooks reduce accidents (PHI or credentials leaving, risky commands) and ask before sensitive actions. They do not stop a determined user or a model that is actively working around them.

In scope: a way to get a hook to allow something it documents as blocked, a secret or PHI shape the scanners should catch and miss, the installer or connectors sending credentials somewhere unintended, unsafe file handling in the scripts.

## Out of scope

- Native Windows (unsupported; use WSL).
- chromadb server mode (unsupported). Advisories in chromadb itself belong with that project.
- Problems that need an attacker who already controls your machine, your shell profile or your Claude Code settings.
- Behaviour documented as a known limit in the README section "Safeguards and their limits".

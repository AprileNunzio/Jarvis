# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

The Jarvis ecosystem applies a strict **Zero-Trust** baseline across all ingress gateways, cognitive dispatchers, and edge mesh nodes.

If you discover a security vulnerability within the codebase, please **do not open a public issue**. Instead, follow this responsible disclosure procedure:

1. Send an email with complete reproduction steps and proof-of-concept to:  
   `security@nunziotech.com` or directly contact `aprilenunzio88@gmail.com`.
2. Encrypt sensitive payloads using the project's PGP key if applicable.
3. You will receive an acknowledgment within 24 hours followed by a prioritized mitigation patch.

All security fixes are thoroughly tested in sandboxed isolation before being deployed to the release pipeline.

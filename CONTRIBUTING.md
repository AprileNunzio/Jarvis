# Contributing to Jarvis

Thank you for your interest in contributing to **Jarvis**, the Autonomous Cognitive Orchestrator engineered by **NunzioTech**.

## Architectural Standards

All contributions must strictly adhere to the following principles:

1. **Clean Architecture & Separation of Concerns (SoC)**:
   - Business logic must remain isolated from frameworks, infrastructure, and delivery mechanisms.
   - Respect the Single Responsibility Principle (SRP).

2. **Code Purity**:
   - Write self-documenting code through expressive naming, domain models, and strict type hints.
   - Do not include explanatory or inline comments within the source code unless explicitly requested.

3. **Structural Limits**:
   - No individual source file may exceed 500 lines. Split large units into dedicated sub-modules.

4. **Zero-Trust Security**:
   - Every endpoint, RPC call, and input must be sanitized and authenticated.
   - Prevent all OWASP Top 10 vulnerabilities (Injection, Broken Access Control, Cryptographic Failures).

5. **Colocation & Feature-Based Layout**:
   - Organize files by feature/domain context rather than generic technical layers.

## Pull Request Process

1. Fork the repository and create your feature branch:
   ```bash
   git checkout -b feature/amazing-cognitive-agent
   ```
2. Ensure all tests and static analysis pass:
   ```bash
   python -m py_compile $(find server -name "*.py")
   ```
3. Submit a pull request detailing the feature, architectural impact, and verification steps.

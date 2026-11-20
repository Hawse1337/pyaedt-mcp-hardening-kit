# Guard release 0.3.2

This repository ships the current `ansys-aedt-mcp` guard release.

- Version: 0.3.2 (2026-11-20)
- Runtime: PyAEDT 1.10.0, AEDT 2026 R1
- Source: https://github.com/Hawse1337/ansys-aedt-mcp
- Assets: wheel, sdist, and `ansys-aedt-mcp-0.3.2-source.zip` attached to the `v0.3.2` release here.

## Why 0.3.2

Security hardening after a real incident where an agent bypassed the guard by launching
`ansysedt.exe` and driving PyAEDT directly from a shell:

- managed-session registry and managed-only attach (unmanaged sessions are refused and reported);
- unmanaged AEDT detection in `guard_status`;
- `run_python_code` / `run_python_script` refused by default (MCP and worker layers);
- run-token scope binding, solve-entry coverage, guarded-run audit;
- launch/release audit with enforcement-mode fields; PyAEDT app identity verification;
- fail-closed client setup for DeepSeek Harness and Codex (`docs/CLIENTS.md`);
- threat model documenting residual same-user/OS-isolation limits.

## Legacy kit

The v1.x branches (v1.4.0-rc1 and earlier) are the older "hardening patch overlay" for a pinned
legacy AEDT MCP checkout. They remain available for historical reproduction; new deployments should
use the v0.3.2 assets above.

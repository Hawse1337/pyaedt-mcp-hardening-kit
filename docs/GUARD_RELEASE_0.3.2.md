# Guard release 0.3.2 — what changed

**ansys-aedt-mcp 0.3.2** is the guarded AEDT automation layer built on the official
[PyAEDT-MCP](https://github.com/ansys/pyaedt-mcp). It is the security-hardened release that followed a
real incident in which an agent bypassed the guard by launching `ansysedt.exe` and driving PyAEDT
directly from a shell.

## Highlights

- **Managed sessions.** Guard-launched AEDT sessions are recorded with PID, process creation time,
  gRPC port, launch source and a `verified` flag. Attaching to an unmanaged session is refused.
  Port attaches resolve the real listener owner and compare it with the record.
- **Unmanaged-session visibility.** `guard_status` classifies every live `ansysedt.exe` as managed or
  unmanaged and reports `scan.enforcement`; status reads are non-mutating.
- **Arbitrary code off by default.** `run_python_code` / `run_python_script` are refused at the MCP
  surface and at the worker backend; only an explicit human operator opt-in enables them.
- **Token-scoped solves.** With `AEDT_GUARD_ENFORCE=1`, analysis submissions require a run token
  bound to project/design/setup; omitted identity is not a wildcard, and a setup-scoped token cannot
  authorise `analyze_all_designs`. WR90 `solve=True`, script bodies and guarded extra setups are
  covered.
- **Audit.** Launch and release events, plus guarded-run adapter commands, are written to the guard
  audit log with enforcement-mode fields; `guard_status` reports sink health and malformed-line
  detection is surfaced by `summarize`.
- **App identity verification.** New PyAEDT app objects are checked against the verified desktop's
  `aedt_process_id`/`port`, closing the vendor fallback-launch path.
- **Path guards.** Export/screenshot/save tools refuse output paths inside the guard state directory.
- **Launcher hardening.** AEDT must be launched from a configured AEDT root; failed launches drop
  their registry record while duplicate-launch protection is retained.
- **Client fail-closed.** Ready-to-use DeepSeek Harness MCP bundle and Codex `config.toml`/`AGENTS.md`
  that require the guard, prompt for MCP tool approval, disable arbitrary code tools, and forbid
  direct PyAEDT/`ansysedt.exe` fallback.

## Verification

- Offline suite: **469 passed, 1 skipped, 118 subtests**.
- Live on AEDT 2026 R1 / PyAEDT 1.10.0: unmanaged PID attach refused; guard-launched session reports
  `managed: true`, can be attached and closed; `run_python_code` returns `refused` without printing
  an enable recipe.
- Source archive attached here corresponds to the tagged source.

## Upgrade notes

- Deployments that attached to a user-opened AEDT session now need either to launch through the guard
  or an explicit human operator decision (`AEDT_MCP_ALLOW_UNMANAGED`).
- Automation that used `run_python_code` / `run_python_script` through MCP must move to dedicated
  tools; enable arbitrary code only for a supervised session.
- Restart the MCP client after upgrading so the new server code and client configuration load.

## Assets

- `ansys_aedt_mcp-0.3.2-py3-none-any.whl`
- `ansys_aedt_mcp-0.3.2.tar.gz`
- `ansys-aedt-mcp-0.3.2-source.zip`
- `v0.3.2.SHA256SUMS.txt`

## Links

- Official upstream: https://github.com/ansys/pyaedt-mcp
- Guard source / issues: https://github.com/Hawse1337/ansys-aedt-mcp
- Threat model: https://github.com/Hawse1337/ansys-aedt-mcp/blob/main/docs/THREAT_MODEL.md
- Client integration (DSH / Codex): https://github.com/Hawse1337/ansys-aedt-mcp/blob/main/docs/CLIENTS.md

## Residual risk

The guard is not an OS sandbox: a same-user shell can still start AEDT directly, and the registry/audit
files are same-user-writable integrity controls. For a hard boundary, isolate the solver at OS level
(separate account/VM, AppLocker/WDAC) and expose only the guard service.

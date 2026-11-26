# Guard release 1.6.1 — what changed

**ansys-aedt-mcp 1.6.1** is the guarded AEDT automation layer built on the official
[PyAEDT-MCP](https://github.com/ansys/pyaedt-mcp), continuing the v0.3.2 managed-session and
fail-closed baseline.

## Highlights

- **Attach-by-port fix.** `open_project` / `export_report_image` no longer pass a stale version to
  an already verified gRPC session, removing the spurious `version specified ... doesn't correspond
  to the pid` error.
- **Custom native report images.** `report_specs` creates arbitrary read-only AEDT reports
  (category, expressions, plot type, variations, context) without arbitrary code or builder
  approval.
- **Native trace overlays.** `overlay_specs` uses `CopyTracesData` + `PasteTraces` to combine
  traces whose primary sweeps differ (for example E-plane Theta and H-plane Phi) in one native
  report.
- **Equal-brightness overlay workflow.** `keep_report=True` keeps the report; save/reopen the
  project and export it by `report_name` to clear AEDT's pasted-trace selection highlight.
- **Far-field sphere setup.** `set_infinite_sphere` edits the named Radiation/InfiniteSphere field
  setup with no builder approval and `requires_resolve=false`; no FEM re-solve is needed.
- **Solve control.** `abort_analysis` is exposed as an MCP tool.
- **Builder approval.** First registration of new builders (`request_type="new_builder"`),
  approval metadata fix, GUI v1.7.1 pending-inbox refresh and stale-request cleanup.

## Verification

- Offline suite: **525 passed, 1 skipped, 118 subtests**.
- Live on AEDT 2026 R1 / PyAEDT 1.10.0: native E360, H polar, 3D, and E+H overlay exported;
  `set_infinite_sphere` updated in place; `keep_report` + save/reopen produced equal-brightness
  traces.

## Assets

- `ansys_aedt_mcp-1.6.1-py3-none-any.whl`
- `ansys_aedt_mcp-1.6.1.tar.gz`
- `ansys-aedt-mcp-1.6.1-source.zip`
- `AEDT.Builder.Approver.exe`
- `v1.6.1.SHA256SUMS.txt`

## Links

- Guard source / issues: https://github.com/Hawse1337/ansys-aedt-mcp
- Official upstream: https://github.com/ansys/pyaedt-mcp
- Threat model: https://github.com/Hawse1337/ansys-aedt-mcp/blob/main/docs/THREAT_MODEL.md
- Client integration: https://github.com/Hawse1337/ansys-aedt-mcp/blob/main/docs/CLIENTS.md

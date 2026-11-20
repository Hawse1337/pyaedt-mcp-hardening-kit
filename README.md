# PyAEDT-MCP Guard — releases

<p>
  <a href="https://github.com/Hawse1337/ansys-aedt-mcp"><img alt="source" src="https://img.shields.io/badge/source-ansys--aedt--mcp-e4572e"></a>
  <a href="https://github.com/ansys/pyaedt-mcp"><img alt="official PyAEDT-MCP" src="https://img.shields.io/badge/upstream-ansys%2Fpyaedt--mcp-2a9d8f"></a>
  <a href="LICENSE"><img alt="license: MIT" src="https://img.shields.io/badge/license-MIT-2a9d8f"></a>
</p>

## 当前守卫发布：v0.3.2（2026-11-20）

这是守卫系统（guarded AEDT automation）的**发布地址**。最新版本 **v0.3.2** 的资产在本仓库
[v0.3.2 release](https://github.com/Hawse1337/pyaedt-mcp-hardening-kit/releases/tag/v0.3.2)：

| 资产 | 说明 |
|---|---|
| `ansys_aedt_mcp-0.3.2-py3-none-any.whl` | Python wheel（PyAEDT 1.10.0，AEDT 2026 R1） |
| `ansys_aedt_mcp-0.3.2.tar.gz` | sdist |
| `ansys-aedt-mcp-0.3.2-source.zip` | 完整源码快照 |
| `v0.3.2.SHA256SUMS.txt` | 校验和 |

完整开发仓库：**https://github.com/Hawse1337/ansys-aedt-mcp**

## Upstream: official PyAEDT-MCP

本守卫基于并面向 **Ansys 官方 PyAEDT-MCP**：
**https://github.com/ansys/pyaedt-mcp**（Apache-2.0）。

- 官方仓库：https://github.com/ansys/pyaedt-mcp
- PyAEDT 文档：https://aedt.docs.pyansys.com/version/stable/index.html
- 本守卫的安装、工具面与安全说明见源仓库的
  [README](https://github.com/Hawse1337/ansys-aedt-mcp#readme)。

## What this guard adds

在官方 PyAEDT-MCP 之上，v0.3.2 增加了生命周期与证据层的防护：

- **managed-only AEDT 会话**：只允许挂载 guard 自己启动的会话；未受管会话会被拒绝并在
  `guard_status` 中列出；
- **任意代码默认关闭**：`run_python_code` / `run_python_script` 在 MCP 与 worker 两层默认拒绝，
  需人类操作员显式开启；
- **run-token 作用域**：`AEDT_GUARD_ENFORCE=1` 时求解提交绑定 project/design/setup；
- **审计与身份校验**：启动/释放事件审计，PyAEDT app 对象与已验证桌面做身份比对。

安全边界与残余风险：
[THREAT_MODEL](https://github.com/Hawse1337/ansys-aedt-mcp/blob/main/docs/THREAT_MODEL.md)；
DeepSeek Harness / Codex 的 fail-closed 配置：
[CLIENTS](https://github.com/Hawse1337/ansys-aedt-mcp/blob/main/docs/CLIENTS.md)。

## 说明

- 守卫**不是 OS 沙箱**：同用户裸 shell 仍可直接启动 AEDT；要硬边界请使用独立账号/VM 与
  AppLocker/WDAC，仅暴露 guard 服务。
- 仓库历史中的 v1.4.0-rc1 及更早 release 是旧的加固补丁套件，仅保留用于历史复现，不再维护；
  新部署请使用上方 v0.3.2 资产。

MIT licensed for this repository's own files.

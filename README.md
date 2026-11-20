# PyAEDT-MCP Guard — releases

<p>
  <a href="https://github.com/Hawse1337/ansys-aedt-mcp"><img alt="source" src="https://img.shields.io/badge/source-ansys--aedt--mcp-e4572e"></a>
  <a href="https://github.com/ansys/pyaedt-mcp"><img alt="official PyAEDT-MCP" src="https://img.shields.io/badge/upstream-ansys%2Fpyaedt--mcp-2a9d8f"></a>
  <a href="https://github.com/Hawse1337/pyaedt-mcp-hardening-kit/releases/latest"><img alt="release" src="https://img.shields.io/github/v/release/Hawse1337/pyaedt-mcp-hardening-kit?color=e4572e"></a>
  <a href="LICENSE"><img alt="license: MIT" src="https://img.shields.io/badge/license-MIT-2a9d8f"></a>
  <img alt="AEDT 2026 R1" src="https://img.shields.io/badge/AEDT-2026%20R1-23262b">
  <img alt="PyAEDT 1.10.0" src="https://img.shields.io/badge/PyAEDT-1.10.0-23262b">
</p>

## 这是什么

这是 **guarded AEDT automation**（受控的 Ansys Electronics Desktop 自动化）的**发布地址**：
在 Ansys 官方 [PyAEDT-MCP](https://github.com/ansys/pyaedt-mcp)（Apache-2.0）之上，增加一层
生命周期与证据防护，让 agent 或脚本**只能**通过受控的 AEDT 会话来建模、求解和导出。

完整开发仓库（源码、测试、issue、威胁模型）：

> **https://github.com/Hawse1337/ansys-aedt-mcp**

本仓库只负责发布：每个版本附带 wheel、sdist、完整源码快照与 SHA-256 校验和。

## 当前发布：v0.3.2（2026-11-20）

[v0.3.2 release](https://github.com/Hawse1337/pyaedt-mcp-hardening-kit/releases/tag/v0.3.2)
包含：

| 资产 | 用途 |
|---|---|
| `ansys_aedt_mcp-0.3.2-py3-none-any.whl` | Python wheel（安装到 guard 的虚拟环境） |
| `ansys_aedt_mcp-0.3.2.tar.gz` | sdist（从源码构建） |
| `ansys-aedt-mcp-0.3.2-source.zip` | 完整源码快照（与 tag 一致） |
| `v0.3.2.SHA256SUMS.txt` | 上述文件的 SHA-256 |

### 快速安装

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install "ansys_aedt_mcp-0.3.2-py3-none-any.whl"
```

要求：Python 3.10+、PyAEDT 1.10.0、AEDT 2026 R1。MCP 客户端配置见
[源仓库的 CLIENTS 指南](https://github.com/Hawse1337/ansys-aedt-mcp/blob/main/docs/CLIENTS.md)。

## v0.3.2 改进了什么

v0.3.2 是**真实 agent 绕过守卫事件**之后的安全加固版。当时的问题不是 guard 被攻破，而是
agent 在 guard 不在执行链路上时直接用 shell 启动了 `ansysedt.exe` 并驱动 PyAEDT。这一版把
"绕过"从不可见变成**被记录、被拒绝**，并补齐了客户端侧的 fail-closed 配置。

### 1. 受管会话（managed sessions）

- guard 启动 AEDT 时记录 PID、进程创建时间、gRPC 端口、启动来源和 `verified` 标记；
- **只允许挂载 guard 自己启动的会话**：`connect_to_aedt` / PyAEDT attach 会拒绝未受管 PID/端口；
- 端口挂载会解析真实监听者 PID，并与 registry 中的记录逐项比对（PID、create_time、端口归属）；
- registry 使用跨进程文件锁、唯一临时文件 + `fsync` + 原子替换，并发启动不会丢记录；
- 启动失败会回收记录，同时保留"防止重复启动"的保护。

### 2. 未受管会话检测

- `guard_status` 把每一个存活的 `ansysedt.exe` 分类为 managed / unmanaged；
- `check_aedt_status` 同样返回 `scan.enforcement` 与 `scan.unmanaged`；
- 状态查询是只读的，不会改写 registry。

### 3. 任意代码默认关闭

- `run_python_code` / `run_python_script` 在 **MCP 层与 worker 后端两层**默认拒绝；
- 只有人类操作员显式设置 `AEDT_MCP_ALLOW_ARBITRARY_CODE` 才可开启；
- 拒绝信息不再给出开启方法，避免自动化 agent 自行"解决"限制。

### 4. 求解入口与 run-token 作用域

- `AEDT_GUARD_ENFORCE=1` 时，analysis 提交需要绑定 project/design/setup 的 run token；
- 省略身份字段不再被当作通配符；setup 级 token 不能授权 `analyze_all_designs`；
- `build_wr90_waveguide(solve=True)`、脚本内 Analyze、guarded run 的额外 setup 都纳入检查。

### 5. 审计与身份校验

- launch / release 事件写入 guard-wide audit；
- guarded-run adapter 命令（preflight、finalize、export…）也写入审计；
- 每行审计带 `enforcement_enabled` / `allow_unmanaged` / `arbitrary_code_allowed`；
- `guard_status` 报告审计文件是否存在、大小与最后写入时间，`summarize` 会报告 malformed 行；
- 新建 PyAEDT app 对象后校验 `desktop_class.aedt_process_id/port` 与已验证桌面一致，堵住
  vendor fallback launch。

### 6. 输出路径与启动路径加固

- `export_results` / `export_config` / `screenshot` / `save_project` 拒绝写入 guard 状态目录；
- launcher 只允许从配置的 AEDT 安装根目录启动（`AEDT_INSTALL_DIR` / `ANSYSEM_ROOTxxx` / 标准产品目录）。

### 7. 客户端 fail-closed

- **DeepSeek Harness**：可安装的 MCP bundle（`mcp__aedt__*`），全局 `AGENTS.md` 强制"先
  `guard_status`，工具缺失就停"，bundle 带调用超时，出厂 skill 已删除所有直连/清理建议；
- **Codex**：`[mcp_servers."ansys-aedt"]` 配 `required = true`、
  `default_tools_approval_mode = "prompt"`，默认禁用 `run_python_code` / `run_python_script`；
- 两个客户端都列出六个**不得由 agent 自行设置**的守卫环境变量。

### 8. 验证

- 守卫离线测试：**469 passed, 1 skipped, 118 subtests**；
- 实机（AEDT 2026 R1 / PyAEDT 1.10.0）：未受管 PID 被拒绝；guard 启动的会话 `managed: true`
  可挂载、可关闭；`run_python_code` 返回 `refused`；
- 本仓库 v0.3.2 资产提供完整源码快照，可与 tag 对照。

## 上游与参考

| 项目 | 链接 |
|---|---|
| 官方 PyAEDT-MCP（上游） | https://github.com/ansys/pyaedt-mcp |
| PyAEDT 文档 | https://aedt.docs.pyansys.com/version/stable/index.html |
| 守卫源码 / 问题反馈 | https://github.com/Hawse1337/ansys-aedt-mcp |
| 威胁模型 | https://github.com/Hawse1337/ansys-aedt-mcp/blob/main/docs/THREAT_MODEL.md |
| 客户端接入（DSH / Codex） | https://github.com/Hawse1337/ansys-aedt-mcp/blob/main/docs/CLIENTS.md |

## 安全边界（请先读）

守卫是**生命周期与证据层的完整性控制，不是操作系统沙箱**：

- 同一 Windows 用户下的裸 shell 仍可以直接启动 AEDT；guard 会把它标记为 unmanaged 并拒绝
  协作，但不能物理阻止；
- registry 与 audit 文件同用户可写，属于"可见性/完整性"证据，不是安全边界；
- 要硬边界：独立账号或 VM 运行 AEDT，配合 AppLocker/WDAC 禁止 agent 账号执行 `ansysedt.exe`，
  仅暴露 guard 服务；或使用远端 solver 服务。

## 历史版本

仓库中的 `v1.4.0-rc1` 及更早 release 是旧的加固补丁套件，仅保留用于历史复现，不再维护。
新部署请使用 v0.3.2 资产。

## License

本仓库自有文件为 MIT。wheel/sdist/源码中的第三方组件遵循其各自许可证；上游 PyAEDT-MCP 为
Apache-2.0。

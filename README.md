# PyAEDT-MCP Hardening Kit

**已发布预览版：[v1.4.0-rc1](https://github.com/Hawse1337/pyaedt-mcp-hardening-kit/releases/tag/v1.4.0-rc1)**

[下载 ZIP 安装包](https://github.com/Hawse1337/pyaedt-mcp-hardening-kit/releases/download/v1.4.0-rc1/pyaedt-mcp-hardening-kit-v1.4.0-rc1.zip) · [下载 SHA256 校验文件](https://raw.githubusercontent.com/Hawse1337/pyaedt-mcp-hardening-kit/main/checksums/v1.4.0-rc1.sha256) · [查看发行说明](https://github.com/Hawse1337/pyaedt-mcp-hardening-kit/releases/tag/v1.4.0-rc1)

这是候选预览版（Pre-release），完整求解与长跑回归尚未完成。

Reliability patches for a pinned legacy AEDT MCP: bounded startup, timeout recovery, project guards, and solve evidence.

**针对 [CAE-Agent-Hub / AEDT MCP](https://github.com/Cai-aa/CAE-Agent-Hub/tree/194ef498e6efb1984cd65325e21e71087588a581/MCP/Ansys/AEDT%20MCP) 的固定旧版本；不是完整 MCP 服务，也不表示兼容所有同名项目。**

| 项目 | 当前状态 |
|---|---|
| 版本 | 已发布候选版 [v1.4.0-rc1](https://github.com/Hawse1337/pyaedt-mcp-hardening-kit/releases/tag/v1.4.0-rc1) |
| 上游 | `Cai-aa/CAE-Agent-Hub`，提交 `194ef498e6efb1984cd65325e21e71087588a581` |
| 许可证 | [MIT](LICENSE)，保留上游 `Thompson Labs` 署名 |
| 验证 | 267 项离线测试；独立 AEDT 2026 R1 无界面连接烟测 |
| 发行说明 | [已发布的发行版及附件](https://github.com/Hawse1337/pyaedt-mcp-hardening-kit/releases/tag/v1.4.0-rc1) |

新用户先看 [取得正确的目标服务](UPSTREAM.md)，再按下面步骤安装。`--repo` 指上游 **MCP/Ansys/AEDT MCP** 子目录，不是本补丁目录。


**v1.4.0-rc1 · 2026-11-06 · 发布候选版**

这是针对指定旧版 AEDT MCP 源码的加固补丁，包含可审查的 Python 载荷、安装器和离线回归测试。它不是完整 MCP 服务；使用者仍需自行安装外部依赖并具备有效的 AEDT 软件授权。

本版集中处理连接失败反复拉起进程、请求超时后重复执行，以及误把 API 成功或旧结果当作求解完成的问题。安装器同时改进了版本识别、换行符兼容和失败恢复。

## 验证范围

已验证的环境基线是 Windows、Python 3.14.10、PyAEDT 1.9.0、MCP SDK 1.30.0。具体测试和证据见 [VALIDATION.md](VALIDATION.md)。

- 新代码已通过离线 mock 回归，并用已有的真实 HFSS profile/convergence 导出验证解析器。
- 已完成一次独立空白桌面的实机无界面启动、gRPC 握手、空工程查询和正常关闭。**求解、建模及长跑的完整实机回归尚未完成**；这次连接烟测不能保证所有环境或软件版本可用。
- attach 保护依赖经过审查的 PyAEDT **1.9.0** 内部实现，其他 PyAEDT 版本会被拒绝，需要先审查并适配。
- 安装兼容性由 `manifest.json` 中逐文件及支撑文件的 hash 决定。版本号相近不代表可以覆盖；未知基线或本地改动应人工合并。

本次制作发布包没有替换开发机上正在使用的 MCP 服务。

可先运行 `python verify_release.py`，校验包内完整性并运行不接触 AEDT 的安装器专项测试。校验和用于发现文件损坏，不是发布者身份签名。

## 安装

全新环境先在专用虚拟环境中安装经过测试的依赖：`python -m pip install mcp==1.30.0 pyaedt==1.9.0 "psutil>=5.9,<8"`。再执行补丁安装，最后对目标上游子目录运行 `pip install -e`。安装器会立即运行离线测试；不要先对尚未修正依赖声明的旧上游运行 pip。

先完整备份目标仓库及配置，在其工作空闲后操作。下面的 `<repo>`、`<venv>` 分别替换为目标仓库和 Python 虚拟环境的绝对路径；命令在本套件目录运行。

```powershell
& "<venv>\Scripts\python.exe" install.py --check --pyproject --pyaedt --repo "<repo>"
& "<venv>\Scripts\python.exe" install.py --install --pyproject --pyaedt --repo "<repo>"
```

`--check` 不安装文件；非零退出时先查看差异。`--install` 对所有目标完成预检后才开始写入。它会：

1. 严格校验包内 payload 的字节 SHA256，并核对目标与支撑文件基线。
2. 对声明为文本的目标容忍已知内容的 CRLF/LF 差异；这项容忍不适用于包内 payload，也不会忽略其他内容修改。
3. 建立唯一批次备份及 `journal.json`，每个目标通过临时文件和原子替换写入。
4. 在捕获到写入错误时尽力恢复本批次；若目标已被并发修改，保留该修改并记录冲突。
5. 运行安装后检查与离线测试。详细结果以退出码及输出为准。

`--pyproject --pyaedt` 修改已识别的依赖声明，并幂等加入 `aedt_project_guard`、`solve_evidence` 到明确的 `setuptools.py-modules` 列表；不认识的配置会被拒绝。它不会自动执行 pip。检查修改后，在目标虚拟环境更新安装：

```powershell
& "<venv>\Scripts\python.exe" -m pip install -e "<repo>"
& "<venv>\Scripts\python.exe" -c "from importlib.metadata import version; print('pyaedt', version('pyaedt')); print('mcp', version('mcp'))"
& "<venv>\Scripts\python.exe" install.py --check --tests --pyproject --pyaedt --repo "<repo>"
```

依赖约束是针对所列基线的兼容配置，不是对未来 SDK 的通用规则。确认 MCP 服务及 broker 的工作空闲后，重启明确的目标服务，再检查实际进程和工具接口；仅保存客户端配置不保证现有进程已更新。

## 失败与恢复

备份位于目标仓库的 `.aedt-hardening-backups/<batch>/`。根据该批次的 `journal.json` 和 `before/` 核查文件，保留安装输出及原始备份。

安装是逐文件原子替换，**不是多文件的崩溃原子事务**。断电、进程被强制结束、磁盘或权限故障可能留下部分安装；安装后测试失败也不代表文件已经自动恢复。检查日志后再决定如何恢复，避免覆盖安装之后的工作。

`--force`、`--revert` 均禁用。不要混用不同批次的备份，也不要因看到锁文件就直接删除它；先核实所属进程和批次状态。

## 使用变化

### 明确连接目标

每次操作只指定一个已核实的本机 AEDT PID 或 gRPC 端口。attach 保护会检查进程身份，并阻止所审查 PyAEDT 路径中的失败回退启动。它不保护任意 `run_python_code` 中自行启动的进程或独立脚本。

`launch_aedt` 等待阶段只做被动端口检查，端口就绪后只对本次刚启动的 PID 进行一次握手；启动或握手失败不再循环创建 broker。未成功握手且仍存活的进程会保留并报告 PID/端口，同一个 launcher 的后续启动会拒绝继续堆叠。检查现有会话再选择显式附着或处理该进程。

端口由实际环境决定；本套件没有“只能使用某个固定端口”的通用要求。端口无法证明所有权时，检查会话并使用明确 PID。

### 超时后先确认原请求

worker 请求超时不等于 AEDT 操作已停止。本版保留 broker 和未完成请求：

- 后续调用若原请求仍未返回，只报告 pending，不提交新命令。
- 若已返回，先通过 recovered 提示交回旧响应，不执行这次调用携带的新命令。
- broker 退出或结果无法确认时，保留“原操作结果未知”的状态，先核对工程、日志和副作用。

回收旧响应不等于这次新命令已执行。特别是保存、建模、提交求解等操作，不要因超时直接重放。此保护只覆盖同一存活服务中的已知 broker；服务重启后仍需核对未完成操作。

### 区分打开和创建工程

Python 辅助 API 位于 `aedt_project_guard`：

| 操作 | 调用 | 条件 |
|---|---|---|
| 打开已有工程 | `open_project(App, absolute_existing_path, **connection_kwargs)` | 已核实的绝对路径必须存在 |
| 创建新工程 | `create_project(App, absolute_new_path, **connection_kwargs)` | 目标工程、锁、同名结果目录均不能已存在 |

使用应用类前先执行 `aedt_project_guard.install()`，再导入 PyAEDT 应用类。旧的裸名称用法只在配置搜索目录和当前目录中解析唯一匹配；重名或缺失均拒绝。旧的 `AEDT_GUARD_ALLOW_CREATE=1` 仍是兼容入口，建议改用显式创建 API。

`project=None` 或空值保留 PyAEDT 的活动工程行为；**不保证选中了预期桌面或工程**。guard 不是文件锁、备份系统或保存拦截器，存在并发写入时仍不能保证安全；应使用独立目录和单一写入者。

### 求解与结果证据

交互求解默认不先保存。部分环境中保存会改变 Solver Type；显式要求保存时，若已经读到的原生 HFSS 求解器类型或频率发生变化或无法再读回，本版停止提交并报告。

`setup_readback` 是原生属性快照，不使用 PyAEDT 缓存冒充原生读回。不支持该 HFSS 属性接口时会明确未确认；其他求解器不套用 HFSS 属性。batch 路径可能在快照后由 PyAEDT 内部保存，其最终设置须查看原生求解记录。

API 返回成功、桌面空闲、已有 LastAdaptive 或导出文件存在，都不足以确认本次求解完成和收敛。`solver_completion_confirmed`、`convergence_confirmed` 保持 false；结合本次提交身份、实际频率、原生 profile 和收敛记录判断。`analyze_all` 的 API 返回值改由 `api_returned_success` 表示，不再把它写成 `completed=true`。

`solve_evidence` 只概括英文原生 profile 和单频 `Max Mag. Delta S` 收敛表。即使表内达标，`latest_submission_linked` 仍为 false；未知、局部或其他格式保持 inconclusive。它不验证扫频、方向图、功率闭合或跨版本模型一致性。

## 其他文件

- [CHANGELOG.md](CHANGELOG.md)：版本变化。
- [发布说明](docs/RELEASE_NOTES_1.4.md)：兼容性和已知边界。
- [客户端配置示例](config/mcp-client-examples.md)：启动环境与超时。
- [NOTICE.md](NOTICE.md)：来源与发布授权状态。

本项目按 [MIT](LICENSE) 许可提供，保留上游 Thompson Labs 的版权声明；来源与改动范围见 [NOTICE](NOTICE.md) 和 [UPSTREAM](UPSTREAM.md)。

## 参与、反馈与发布教程

- [贡献与复验](CONTRIBUTING.md)
- [首次发布与以后更新教程](docs/GITHUB_PUBLISH_TUTORIAL.md)
- [Release 正文](docs/RELEASE_DRAFT.md)

这是一套独立的社区补丁，与 Ansys、PyAEDT 或上游项目没有官方隶属或背书关系。

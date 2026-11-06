# v1.4.0-rc1 验证记录

日期：2026-11-06。环境：Windows、Python 3.14.10、PyAEDT 1.9.0、MCP SDK 1.30.0。wheel 构建使用本地 setuptools 84.2.1；这不是对其他版本的兼容承诺。

| 验证 | 结果 | 范围 |
|---|---|---|
| 完整离线回归 | 245 项通过，0 失败、0 错误、0 跳过 | 16 个顶层测试模块；不运行 live 目录 |
| 安装器专项 | 22 项通过 | 临时目录：CRLF、真实改动拒绝、路径检查、缺失原文件、幂等、锁、批次回滚和并发修改保护 |
| 隔离安装 | 通过 | 已知旧原始快照及 v1.3 安装快照；逐文件和支撑模块 hash 匹配后安装，不改在用服务 |
| wheel 构建与导入 | 通过 | 确认 guard、solve_evidence、worker_client、backend 等实际进入 wheel，且可从 wheel 导入 |
| 真实历史导出解析 | 通过 | 对已有小算例的原生 profile/convergence 只读核对，未把旧解关联为新任务 |
| AEDT 2026 R1 实机连接烟测 | 通过 | 仅一个独立空白无界面进程；核对 PID/端口/版本，查询空项目列表并正常关闭 |

245 项包含本版相关运行时测试；安装后的 manifest 子集是其中一部分，不能再次相加。安装器 22 项是另外的测试，共 267 项离线测试。

实机首次烟测发现端口枚举不能确认监听所有者，保护因此拒绝连接，没有循环拉起进程。将启动握手改为明确自启动 PID 后，复测通过。最终烟测只启动一个进程，使用实际可用的非固定 gRPC 端口；没有打开、新建或求解工程，没有接管已有 AEDT 会话。

## 复验

先在解压后的套件目录运行：

```powershell
python -B verify_release.py
```

这一步仅校验文件和运行安装器专项测试，不导入 PyAEDT、不连接 AEDT。使用目标服务的虚拟环境，在一次性仓库副本验证安装：

```powershell
& "<venv>\Scripts\python.exe" -B install.py --check --pyproject --pyaedt --repo "<disposable-repo>"
& "<venv>\Scripts\python.exe" -B install.py --install --pyproject --pyaedt --repo "<disposable-repo>"
& "<venv>\Scripts\python.exe" -B install.py --check --tests --pyproject --pyaedt --repo "<disposable-repo>"
```

专项测试会故意打印部分 ERROR，以确认坏载荷和错误操作被拒绝；判断应看整体测试结果及进程退出码。检查校验和有助于发现文件变化，不等于发行签名或授权证明。

## 尚未验证

- 新代码下的新建/保存/重新打开工程、完整求解、长时超时、OOM 和大工程恢复的实机端到端回归。
- 其他 PyAEDT、MCP、AEDT、Python 版本及操作系统；特别是新 attach 保护明确只接受已审查的 PyAEDT 1.9.0。
- COM 连接目前有离线测试，最终成功的实机烟测使用 gRPC，不应写成 COM 也已实机通过。
- 本包不修复或解释跨版本电磁结果差异，也没有把 API 成功、空闲或历史文件存在当成新求解完成。

当前在用 MCP 仓库未改动；本次临时实机测试进程已清理，原有 AEDT 会话保持。上游来源与 MIT 原文已核实并保留，见 [UPSTREAM.md](UPSTREAM.md)。候选版标识对应尚未完成的完整求解与长跑回归。

## 上游固定版本安装复验

直接下载上游固定提交模块的 44 个文件并逐项核对 Git blob SHA，在一次性目录安装本补丁：预检、安装均退出 0，146 项安装后测试通过。该 146 项是完整运行时测试的子集，不再次累加到 267。

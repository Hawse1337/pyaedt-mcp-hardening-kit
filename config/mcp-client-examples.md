# MCP 客户端启动环境与超时示例

适用于 v1.4.0-rc1。这里给出环境变量和 stdio 启动示意；各客户端配置文件位置、schema、超时单位和重载方式以实际版本为准。不能直接把一种客户端的配置键用于另一种客户端。

`<repo>` 是完整 MCP 仓库，`<venv>` 是其 Python 虚拟环境，`<AEDT>` 是含 `ansysedt.exe` 的 AEDT 安装目录。使用前替换为本机绝对路径。

## 环境变量

| 变量 | 示例 | 用途 |
|---|---|---|
| `AEDT_VERSION` | `2026.1` | 所选择的 AEDT 版本；不改变 PyAEDT 1.9.0 的保护版本约束 |
| `AEDT_INSTALL_DIR` | `<AEDT>` | 查找 AEDT 可执行文件 |
| `AEDT_WORKER_TIMEOUT` | `1800` | 未显式覆盖时，worker 请求的等待预算，单位秒 |
| `AEDT_LAUNCH_TIMEOUT` | `240` | launcher 的启动等待预算，单位秒 |
| `AEDT_GUARD_SEARCH_DIRS` | `<project-dir-1>;<project-dir-2>` | 可选，裸工程名的搜索目录；重名会拒绝 |

超时值必须是有限正数；单次工具显式传入的 timeout 可能覆盖默认值。服务端等待预算、客户端工具预算、求解器自身任务生命周期是不同概念。较长超时不会使异步求解自动完成。

## 常见 stdio 配置形状

这是示意片段。`mcpServers`、`cwd` 等键是否支持，须检查客户端本身的配置说明；本片段没有经过各客户端实机兼容验证。

```json
{
  "mcpServers": {
    "ansys-aedt": {
      "command": "<venv>\\Scripts\\python.exe",
      "args": ["<repo>\\mcp_server.py"],
      "cwd": "<repo>",
      "env": {
        "AEDT_VERSION": "2026.1",
        "AEDT_INSTALL_DIR": "<AEDT>",
        "AEDT_WORKER_TIMEOUT": "1800",
        "AEDT_LAUNCH_TIMEOUT": "240"
      }
    }
  }
}
```

如果客户端有自己的工具超时，可给它留出大于所需服务端等待预算的余量，并核对单位。没有对应配置项时，不要自行添加未经识别的字段。客户端取消或超时也不能证明 AEDT 操作已经停止。

## PowerShell 启动示意

```powershell
$env:AEDT_VERSION = "2026.1"
$env:AEDT_INSTALL_DIR = "<AEDT>"
$env:AEDT_WORKER_TIMEOUT = "1800"
$env:AEDT_LAUNCH_TIMEOUT = "240"
& "<venv>\Scripts\python.exe" "<repo>\mcp_server.py"
```

stdio 服务应由兼容的 MCP 客户端驱动；直接启动后等待输入不代表故障。

## 检查实际生效的环境

环境变量必须传给实际启动 MCP 服务的进程。仅写入用户级环境变量不保证既有服务或其 broker 已读到。

目标服务空闲并经明确重启后，用已核实的 PID 或端口连接，再执行只读检查：

```python
import os
print("AEDT_WORKER_TIMEOUT =", os.environ.get("AEDT_WORKER_TIMEOUT"))
print("AEDT_LAUNCH_TIMEOUT =", os.environ.get("AEDT_LAUNCH_TIMEOUT"))
```

该检查读取的是 broker 继承的环境，不证明所有工具都采用相同单次等待预算。结合调用参数及服务日志判断，不要用真实工程的长时间写入来测试超时。

## 超时后的处理

本版保留超时请求所属 broker。后续调用先报告原请求 pending，或通过 recovered 提示交回旧响应；这两种情况都没有执行新命令。先核对原请求结果和工程副作用，再决定是否提交下一条命令。

更改代码后需要重启明确的目标服务及其 broker 才能载入新代码。不能通过结束所有同名 Python/AEDT 进程实现更新；先确认归属和未完成工作。

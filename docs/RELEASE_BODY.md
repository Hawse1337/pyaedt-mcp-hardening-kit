## PyAEDT-MCP Hardening Kit v1.4.0-rc1

首个公开发布候选版，为固定旧版 AEDT MCP 提供可靠性加固。适用上游为 Cai-aa/CAE-Agent-Hub 的 AEDT MCP 模块；本套件不是完整 MCP 服务或 Ansys 官方发行版。

### 主要改动

- 启动时被动等待，只对明确 PID 握手一次，限制失败回退启动。
- 超时保留原请求，先恢复旧响应，避免盲目重复提交。
- 加强工程路径保护，明确区分打开和新建。
- 修复将 API 成功误报为求解完成的问题，增加原生设置和收敛证据检查。
- 改进 CRLF/LF 兼容、批次备份和安装失败恢复。

### 验证结果

- 267 项离线测试通过。
- 固定上游的 LF、CRLF 两份独立目录均安装通过，各 146 项安装后测试通过；该子集不重复累加。
- 一次 AEDT 2026 R1 无界面启动、gRPC 连接、空工程查询和正常关闭通过。
- wheel 构建及新增模块导入检查通过。

验证环境：Windows、Python 3.14.10、PyAEDT 1.9.0、MCP SDK 1.30.0。

### 适用范围

固定上游提交：194ef498e6efb1984cd65325e21e71087588a581。

上游子目录：MCP/Ansys/AEDT MCP。安装以 manifest 文件哈希为准；其他版本需人工审查。新的附着保护仅接受已审查的 PyAEDT 1.9.0。

### 已知限制

完整求解、建模和长跑实机回归尚未完成。API 成功、桌面空闲或旧导出存在，都不能证明最新求解已完成并收敛。本候选包不解释或修复跨版本电磁结果差异。

### 使用与许可

安装前请阅读仓库中的 README、UPSTREAM 和 VALIDATION，并先在隔离副本验证。

MIT 许可，保留上游 Copyright (c) 2026 Thompson Labs；完整许可文本见 LICENSE。

下载 ZIP 及同名 .zip.sha256 核对附件，解压后运行：

`python -B verify_release.py`

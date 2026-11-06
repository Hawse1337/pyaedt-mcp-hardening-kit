# 首次候选发行版

源码提交不等于创建了 GitHub Release。本页提供已准备好的填写内容。

## 复制正文时保留 Markdown

请使用 [纯正文文件](RELEASE_BODY.md) 的 **Copy raw file** 按钮，或打开 [TXT 原文](https://raw.githubusercontent.com/Hawse1337/pyaedt-mcp-hardening-kit/main/docs/RELEASE_BODY.txt) 后全选复制。不要在本页渲染后的段落上直接拖选复制，否则标题的 `##` 和列表的 `-` 可能丢失。

将完整原文粘贴到 Release 的说明编辑框，再切换 **Preview** 检查。正文只包含标题、段落和普通列表；不需要复制本页的操作提示。ZIP 已上传时不必重复上传，也不必在正文里再次粘贴附件链接。

打开 [创建发行版](https://github.com/Hawse1337/pyaedt-mcp-hardening-kit/releases/new)，填写：

- Tag：`v1.4.0-rc1`，Target：包含本候选源码的 `main`。
- Title：`PyAEDT-MCP Hardening Kit v1.4.0-rc1`。
- 勾选 **This is a pre-release**，先用 **Save draft** 可预览。
- 附件：`pyaedt-mcp-hardening-kit-v1.4.0-rc1.zip` 和同名 `.zip.sha256`。

下面的正文可直接复制：

---

## PyAEDT-MCP Hardening Kit v1.4.0-rc1

首个公开发布候选版，针对 `Cai-aa/CAE-Agent-Hub` 中固定旧版 AEDT MCP 提供可靠性加固；不是完整 MCP 服务或 Ansys 官方发行版。

### 主要改动

- 启动被动等待后只对明确 PID 握手一次，限制失败回退启动。
- 超时保留原请求并先恢复旧响应，避免盲目重复提交。
- 加强工程路径检查，明确打开与新建，拒绝重名误指和缺失路径隐式创建。
- 修复 API 成功被误报为求解完成，增加 HFSS 原生设置快照和收敛记录摘要。
- 安装器支持已知文本的 CRLF/LF 差异、批次备份、逐文件原子替换和捕获写入错误后的尽力恢复。

### 已验证

- 267 项离线测试通过。
- 固定上游模块的 LF 与 CRLF 两份独立目录均完成安装，各 146 项安装后测试通过；该子集不重复累加。
- 一次独立 AEDT 2026 R1 无界面启动、gRPC 握手、空工程查询与正常关闭通过。
- wheel 构建及新增模块导入检查通过。

验证环境：Windows、Python 3.14.10、PyAEDT 1.9.0、MCP SDK 1.30.0。新的附着保护仅接受已审查的 PyAEDT 1.9.0。

### 适用范围与已知边界

固定上游为 `Cai-aa/CAE-Agent-Hub` 提交 `194ef498e6efb1984cd65325e21e71087588a581`，子目录 `MCP/Ansys/AEDT MCP`。安装以 manifest 中的哈希为准；其他版本应人工审查。

完整求解、建模与长跑实机回归尚未完成。API 成功、桌面空闲、旧导出存在都不等于最新求解收敛。这个候选包不解释或修复跨版本电磁结果差异。

### 使用与许可

先阅读仓库 README、UPSTREAM 和 VALIDATION，使用隔离副本验证后再部署。MIT 许可，保留上游 `Copyright (c) 2026 Thompson Labs`；完整原文见 LICENSE。

下载附件后可用同名 `.sha256` 核对实际 ZIP，解压后运行 `python -B verify_release.py`。GitHub 自动生成的 Source code ZIP 与人工整理附件可能不同，不能混用其校验值。

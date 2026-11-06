# 上游版本与安装基线

本补丁基于 [https://github.com/Cai-aa/CAE-Agent-Hub](https://github.com/Cai-aa/CAE-Agent-Hub) 的 [AEDT MCP 子目录](https://github.com/Cai-aa/CAE-Agent-Hub/tree/194ef498e6efb1984cd65325e21e71087588a581/MCP/Ansys/AEDT%20MCP)，对应确切 GitHub 提交 `194ef498e6efb1984cd65325e21e71087588a581`。上游 MIT 许可原文已保存在 [LICENSE](LICENSE)，原版权行为 `Copyright (c) 2026 Thompson Labs`。

## 如何取得目标服务

下载 [该固定版本的上游 ZIP](https://github.com/Cai-aa/CAE-Agent-Hub/archive/194ef498e6efb1984cd65325e21e71087588a581.zip)，解压后找到 **MCP/Ansys/AEDT MCP**。这个子目录才是安装命令中 `--repo` 指向的目标；本补丁仓库本身不是完整 MCP 服务。

也可在新目录使用 Git 获取固定版本，再取上述子目录。不要把正在工作的另一个仓库强制重置到该提交。其他版本应先人工比较接口和源文件，不能仅凭名称相似安装。

## 已做的来源核对

- 原始部署基线的 15 个顶层 Python 源文件，与该固定上游版本仅有 CRLF/LF 差别。
- 22 个顶层文件中 20 个在仅统一换行符后完全相同；`.gitignore`、`pyproject.toml` 有部署改动。
- 已直接下载固定版本模块的全部 44 个文件，核对 Git blob SHA，随后在一次性目录完成 `--check`、`--install --pyproject --pyaedt` 和 146 项安装后测试。
- `manifest.json` 同时保留已审查的原始基线、已安装旧补丁基线及文本换行符口径；不忽略其他实质内容变化。

旧材料中的 `f6173fc`、`40b18f5`、`547214d`、`6a8daa7` 是不同阶段的本地记录，不能当作上游 GitHub 提交链接，也不要求新用户拥有这些本地 Git 对象。安装以文件哈希而非提交名称猜测兼容性。

## 后续修改

v1.3 包含旧的工程守卫、busy 对话框保护和交互求解默认不预先保存。v1.4 增加一次启动握手、明确 PID 附着、超时响应恢复、路径检查、原生求解设置/证据检查及安装恢复；最终加固文件并不再与上游原始文件逐字相同。详情见 [变更记录](CHANGELOG.md)。

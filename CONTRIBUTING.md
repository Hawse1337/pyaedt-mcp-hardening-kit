# 贡献与复验

请先读 [UPSTREAM](UPSTREAM.md) 和 [VALIDATION](VALIDATION.md)。这个仓库是针对固定旧基线的补丁，不能用通过 mock 测试来宣称其他 AEDT/PyAEDT 版本已经实机兼容。

提交问题时附 Windows、Python、PyAEDT、MCP SDK、AEDT 版本，所用上游完整提交及脱敏后的错误信息。说明是启动、附着、安装还是求解问题；不要上传访问令牌、许可服务器地址、私人路径、完整用户工程或包含这些数据的日志。

普通说明和安装器自检不需要 AEDT：

```powershell
python -B verify_release.py
```

文档更新后，用以下命令更新已列入发布清单的文件校验和，再自检：

```powershell
python -B tools/refresh_checksums.py
python -B verify_release.py
```

`RELEASE_FILES.json` 是明确的发布文件白名单。新增文件需先审查并加入清单；脚本不会把工作目录中的工程、日志或虚拟环境自动打包。

修改 `files/` 载荷后，先为行为变化做合适的离线回归，审查并更新 `manifest.json` 的安装后哈希，再刷新校验和。不能把任意新上游文件的哈希添加到兼容列表来绕过冲突，也不能通过 `--force` 覆盖。源文件文本应使用 UTF-8、LF，确保 Windows Git 检出后仍能校验。

重要的启动、连接、保存和求解变化还需在独立空白工程/会话完成实机回归，记录实际 PID/版本、原生设置、求解完成和收敛证据。用户正在使用的会话、工程和结果保持独立。

建议先创建分支、提交清楚的变更说明，再通过 Pull Request 合并。发行包的 SHA256 需要与实际附件对应；已对外发布的版本包保持不变，修复通过新版本发布。

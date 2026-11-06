# GitHub 首次发布教程

本教程对应已创建的公开仓库 [Hawse1337/pyaedt-mcp-hardening-kit](https://github.com/Hawse1337/pyaedt-mcp-hardening-kit)，首个候选版本为 `v1.4.0-rc1`。

| 本次操作 | 状态 |
|---|---|
| 公开仓库与初始 README | 已创建，无需再建第二个同名仓库 |
| 完整源码与说明上传 | 已上传并核验 43 个文件；[首次完整提交](https://github.com/Hawse1337/pyaedt-mcp-hardening-kit/commit/8a920ca228b4c466675157d51630eb4d9b817380) |
| GitHub Release | 尚未发布；上传源码不等于已发布发行版 |

本次使用 GitHub 接口上传源码。当前连接器没有创建发行版的接口，因此最后可能需要你在 Releases 页面按第 5 节完成发布。

## 1. 先认清四个名称

| 名称 | 你可以怎样理解 |
|---|---|
| Repository（仓库） | 项目文件、说明文档和修改历史所在的位置 |
| Commit（提交） | 保存一次有说明的文件变更 |
| Tag（标签） | 给某次提交起固定版本名，例如 `v1.4.0-rc1` |
| Release（发行版） | 围绕标签提供版本说明和下载附件 |

上传代码形成提交；给选定提交加标签；再把安装包挂到发行版。它们是不同步骤。[Git 与提交](https://docs.github.com/en/get-started/using-git/about-git)、[GitHub 发行版](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)有更完整的解释。

## 2. 本次仓库信息，以及以后如何新建

本次仓库已经建好。以后创建另一个项目时，登录后点击右上角 **＋ → New repository**，也可以打开 `https://github.com/new`。本次填写内容可作为参考：

| 字段 | 本次建议 |
|---|---|
| Owner | `Hawse1337` |
| Repository name | `pyaedt-mcp-hardening-kit` |
| Description | `Hardening patches for legacy AEDT MCP: safer startup, timeout recovery, project guards, and solve evidence.` |
| Visibility | 本次是 **Public**；需要先自行预览的新项目可选 Private |
| Add README | 本次已初始化 README；后续用准备好的完整说明替换 |
| .gitignore / License 初始化 | 先不自动生成，随后上传已经整理的文件 |

创建其他新仓库时，检查账号和拼写后点 **Create repository**。仓库名不必包含版本号，以后的版本都放在同一仓库里。若准备通过 Git 推送一个已经存在的本地仓库，初始化选项应按导入方式调整，避免与本地历史冲突。[官方创建步骤](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)。

本次已定位上游 `Cai-aa/CAE-Agent-Hub`，其指定提交的 [LICENSE](https://raw.githubusercontent.com/Cai-aa/CAE-Agent-Hub/194ef498e6efb1984cd65325e21e71087588a581/LICENSE) 是 MIT，署名为 `Copyright (c) 2026 Thompson Labs`。本包应随附适用的许可证全文并在 NOTICE 保留来源及署名；沿用 MIT 是有据可查的选择，不是因模板方便就随意勾选。其他项目也应先核对自己的来源。[GitHub 许可证说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)。

## 3. 上传可浏览的源码

进入仓库，空仓库可点 **uploading an existing file**；已有文件时点 **Add file → Upload files**。打开本地清洁发布目录，把**目录里面的内容**拖入网页，等待上传结束。不要把外层目录一起套进去，也不要只传一个 ZIP。[官方上传说明](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)。

仓库首页应直接看到这样的结构：

```text
README.md
LICENSE
CHANGELOG.md
NOTICE.md
VALIDATION.md
install.py
manifest.json
SHA256SUMS.txt
verify_release.py
files/
docs/
config/
```

下方提交说明可填 `Initial import of v1.4.0-rc1 candidate`。首次导入自己的空仓库可提交到 `main`；后续涉及代码的修改适合新分支和 Pull Request，审查通过后合并。完成后点开 `files/` 和 README 中的链接，检查路径是否正确。

只上传清洁发布目录。HFSS 工程及结果、`.env`、`.venv/`、缓存、运行日志、许可证配置和凭据不属于这个仓库；网页上传前直接核对待上传列表。以后用 Git 提交时可配合 `.gitignore`，但它不能自动清除已提交的内容。[GitHub 防止误提交的建议](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)。

## 4. 填好首页说明

根目录的 `README.md` 会显示在仓库首页。本项目应讲清：补丁解决什么问题、它不是完整 MCP 服务、适用版本、安装方式、验证结果和已知限制，避免让读者误以为它是 Ansys 官方产品。[README 官方说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)。

首页右侧 **About** 的齿轮用于编辑简介和 Topics。可以使用 `pyaedt`、`ansys`、`hfss`、`mcp`、`python`、`automation`；没有项目网站时 Website 留空。Topics 使用小写字母、数字和连字符。[Topics 官方说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics)。

## 5. 制作第一个候选发行版

完成源码提交并核验后，打开本仓库的 [新建发行版页面](https://github.com/Hawse1337/pyaedt-mcp-hardening-kit/releases/new)，或从首页进入 **Releases → Draft a new release**：

| 字段 | 本次填写 |
|---|---|
| Tag | 新建 `v1.4.0-rc1` |
| Target | 包含已检查源码的 `main` 分支 |
| Release title | `PyAEDT-MCP Hardening Kit v1.4.0-rc1` |
| Pre-release | 勾选 **This is a pre-release** |

版本说明可从仓库的 [docs/RELEASE_DRAFT.md](https://github.com/Hawse1337/pyaedt-mcp-hardening-kit/blob/main/docs/RELEASE_DRAFT.md) 直接复制。正文参考如下；若该文件尚未上传，先等文件列表核验完成再发布：

```markdown
## PyAEDT-MCP Hardening Kit v1.4.0-rc1

这是面向指定旧版 AEDT MCP 源码的发布候选补丁，不是完整 MCP 服务，也不是 Ansys 官方产品。

### 本版改进
- 启动只对自启动 PID 进行一次握手，核对进程、端口和版本。
- 超时保留原请求，后续先恢复旧响应，避免盲目重复提交。
- 加强工程路径保护，明确区分打开与创建工程。
- 修复将 API 成功误报为求解完成的问题。
- 改进 CRLF 识别、逐文件预检、批次备份和失败恢复。

### 验证与限制
267 项离线测试通过，独立 AEDT 2026 R1 无界面连接与正常关闭烟测通过。
仅对所列旧基线、Windows、Python 3.14.10、PyAEDT 1.9.0 和 MCP SDK 1.30.0 做过验证。
完整求解、建模和长跑实机回归尚未完成，因此作为预发布候选版提供。

### 下载与使用
下载附件 pyaedt-mcp-hardening-kit-v1.4.0-rc1.zip 及同名 .zip.sha256。
校验并解压后，先阅读 README.md，再运行 python -B verify_release.py。
安装前运行 --check；不支持的基线需要人工合并，不要强制覆盖。

完整记录见仓库 README.md、VALIDATION.md 和 CHANGELOG.md。
上游为 Cai-aa/CAE-Agent-Hub，保留 MIT 许可证及 Thompson Labs 署名，见 LICENSE 与 NOTICE.md。
```

在附件区上传 `pyaedt-mcp-hardening-kit-v1.4.0-rc1.zip` 和同名 `.zip.sha256`。等附件上传完成，先点 **Save draft**，复核说明与下载包。确认作为候选版公开后，再点 **Publish release**。`rc1` 表示第一个发布候选版；必须勾选本次的 **This is a pre-release**，不应把它宣传成已完成所有实机回归的稳定版。[官方发行操作](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository?tool=webui)。

**发行版草稿不会把公开仓库的源码变成私有。** 仓库可见性是另一项设置；如果某个项目仍有来源或内容待核实，应保持 Private，而不是仅在公开仓库里存一个草稿。[可见性设置](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)。

## 6. 检查下载包

发布后从 Assets 下载你手工上传的候选 ZIP。GitHub 自动生成的 **Source code (zip)** 是标签源码快照，可能与整理过的安装包不同，不要混用两者的校验值。

在下载目录打开 PowerShell，运行：

```powershell
Get-FileHash .\pyaedt-mcp-hardening-kit-v1.4.0-rc1.zip -Algorithm SHA256
Get-Content .\pyaedt-mcp-hardening-kit-v1.4.0-rc1.zip.sha256
```

比较两行中的 64 位十六进制值，大小写可忽略。解压后再执行 `python -B verify_release.py`。本包内的 SHA256 检查用于发现文件损坏或变化，不是发布者身份签名；GitHub 的不可变发行版还提供独立的[完整性验证机制](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/verify-release-integrity)。

## 7. 下次怎样更新

改说明或代码后创建新的 commit；发布新版本时再创建新 tag 和 Release。例如下一候选版用 `v1.4.0-rc2`，完成正式版验证后用 `v1.4.0`。`main` 后续变化不会自动改写旧标签对应的版本。

打包前同步版本说明、测试记录；若载荷变化，更新 `manifest.json` 中相应 hash，再生成 `SHA256SUMS.txt`、ZIP 和 ZIP 校验文件。不要修改已发布 ZIP 却继续沿用旧校验值。保留上一版，下载者才能明确选择和复现当时的内容。

## 8. 新手常见问题

**为什么网页只有一个压缩包？** 因为只上传了 ZIP。发行附件便于下载，但仓库还应保留解压后的源码结构，让读者能查看差异、阅读安装脚本和报告问题。文件名中出现 `public` 只是本地目录标记，不会自动把 GitHub 仓库变成公开。

**为什么改完 README，旧版本下载没变化？** 首页通常展示 main 的当前文件，发行附件是另一份已上传文件，标签也指向选定提交。确实需要改变交付内容时发布下一候选版，并同步新包和校验值。

**如何知道第一次发布完成？** 首页能浏览源码并正确显示说明，Releases 中能看到带 Pre-release 标记的版本，附件可以重新下载且校验一致，才构成这次候选发布的交付结果。私有仓库还需要给访问者权限；公开仓库则可让未登录者打开项目链接核对。

日常小改动只需提交；准备一批可交付的修改时再发新版本。遇到问题可先记录复现步骤、运行版本和错误摘要，再创建 Issue，不必把全部工程和原始日志都公开。

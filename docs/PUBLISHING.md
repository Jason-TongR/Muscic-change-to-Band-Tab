# GitHub 仓库与 Release 发布指南

[返回 README](../README.md)

仓库地址：[Jason-TongR/Muscic-change-to-Band-Tab](https://github.com/Jason-TongR/Muscic-change-to-Band-Tab)

这份指南面向仓库维护者。README 面向使用者，优先让他们选择操作系统和找到下载入口。

## 1. About 填什么

在仓库首页右侧 About 的编辑入口填写：

**Description（描述，直接复制）：**

> 本地音频转动态乐队谱的桌面工具：AI 分轨、吉他/贝斯指法、逐音校正、慢放循环与项目分享。

**Website（网站）：**

```text
https://github.com/Jason-TongR/Muscic-change-to-Band-Tab/releases
```

还没有发布 Release 时可以先留空，发布后再填写。不要填本机的 localhost / 127.0.0.1 地址。

**Topics（主题标签，逐个添加）：**

```text
music-transcription
audio-transcription
guitar-tabs
demucs
basic-pitch
pyside6
desktop-app
python
```

## 2. Git 仓库提交什么

提交源码和构建所需文件，例如：

- `desktop.py`、`app.py`、`bandtab/`、`web/`。
- `README.md`、`docs/`、`assets/`、`tests/`。
- `scripts/`、`packaging/`、`requirements*.txt`。
- `.github/` 和 `.gitignore`。

当前 `.gitignore` 已排除以下本地生成目录，保持排除即可：

| 目录 | 用途 | 分发方式 |
| --- | --- | --- |
| `release/` | 压缩包、安装程序、校验文件、示例项目 | 挑选需要的文件上传 Release 附件 |
| `dist/`、`build/` | 打包后的程序目录与中间文件 | 发布 `release/` 的完整压缩包，不提交这些目录 |
| `.venv*/`、`.python/`、`.tools/`、`.vendor/`、`.cache/` | 本机依赖、工具和缓存 | 由安装/构建脚本准备，不提交 |
| `data/` | 本机曲库、模型和计算结果 | 软件模型已进入完整发行包；歌曲通过 `.bandtab` 单独分享 |

不要把整个工作文件夹再打成一个 ZIP 当安装包，也不要强制把上面的忽略目录加入 Git。当前 Linux 包约 489 MiB，适合放在 Releases；普通 Git 仓库会阻止超过 100 MiB 的单个文件。[GitHub 大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)

## 3. Windows 这一版 Release 怎么填

Windows 版的应用版本是 **0.2.1**。先等 Windows 工作流成功、确认 `Windows-validation.json` 中的 `status` 为 `pass`，再发布该次构建的附件。

| 字段 | 填写内容 |
| --- | --- |
| Tag | `v0.2.1-preview.1`（已使用则换新标签） |
| Target | 生成本次软件包的提交，见 `build-info-Windows-AMD64.json` 的 `source_revision` |
| Release title | `BandTab Studio v0.2.1-preview.1 · Windows 桌面预览版` |
| Description | 复制[Windows 发布说明](releases/v0.2.1-preview.1.md)全文 |
| This is a pre-release | 勾选 |

在仓库 [Releases](https://github.com/Jason-TongR/Muscic-change-to-Band-Tab/releases) 点击创建新版本，填以上内容。**Target 必须包含 Windows 版源码**；如果还没合并构建分支，不要直接用旧的 `main` 发布新软件包。

### 上传哪些附件

从成功的 Windows 构建页面下载 `BandTabStudio-Windows-x64`，解压 Actions 外层 ZIP，上传里面这 **6 个文件**：

| 文件 | 是否需要 | 用途 |
| --- | --- | --- |
| `BandTabStudio-Windows-x64-Setup.exe` | 必须 | 推荐给普通用户的中文安装程序 |
| `BandTabStudio-Windows-x64-Portable.zip` | 必须 | 免安装完整便携包 |
| `原创练习曲.bandtab` | 建议 | 含音频与预编谱的示例项目 |
| `SHA256SUMS.json` | 必须 | 核对上述两个软件包和示例文件的完整性 |
| `Windows-validation.json` | 建议 | 本次 Windows 安装与模型测试结果 |
| `build-info-Windows-AMD64.json` | 建议 | 应用版本、源码提交、依赖版本与校验记录 |

**不要上传** `dist/` 整个目录、开发环境、日志大包，或 Actions 外层 ZIP。发布说明粘贴到描述框即可，不必再作为附件上传。GitHub 自动提供的 `Source code (zip / tar.gz)` 不是安装程序。

可先保存为草稿，确认文件齐全后发布。预览包未做代码签名，需在说明中保留这一点；云端测试也不能代替真实电脑的扬声器与耳机测试。

### Linux 旧包怎么处理

本地原有 `release/BandTabStudio-Linux-x86_64-glibc2.43.tar.gz` 属于 **0.2.0**，在 Ubuntu 26.04 / glibc 2.43 构建。它的[原发布说明](releases/v0.2.0-preview.1.md)继续保留。不要把旧的 Linux 包改名为 0.2.1，或与 Windows 的新校验文件混用。

不同版本应分别建 Release。以后同一版本需要发布多个系统包时，可以合并各自的校验记录，或者将校验文件改成带系统名的名称，避免同名覆盖。仅记录实际上传的文件。

## 4. 下次怎样重新生成 Windows 包

普通使用者从 Release 下载软件，不需要进行这些步骤。维护者有两种构建方式：

1. **使用 GitHub：** 推送本次源码后，在 Actions 中打开 **Build Windows installer**。相关源码变更会触发；默认分支已有工作流后也可手动运行。成功后下载 `BandTabStudio-Windows-x64`。失败时下载 `BandTabStudio-Windows-diagnostics` 查看日志与截图。
2. **使用 Windows 电脑：** 安装 Python 3.11 x64 与 Inno Setup 6.5 及以上，双击项目根目录的 `build-windows.cmd`。成品在 `release/`。完整操作见 [Windows 构建说明](WINDOWS.md#开发者一键构建)。

专用 Windows 流程会验证：源码测试、完整便携包、中文路径、Windows 原生窗口、离线模型转写、安装与快捷方式、项目打开命令、重复安装及卸载保留曲库。工作流只保存成品，**不会自动发布 Release**。

## 5. macOS 与多平台发布

在 Actions 运行 **Build desktop applications** 可分别构建四个平台。各个平台任务独立；一种平台通过不代表其他平台通过。

| 平台 | 成品文件 |
| --- | --- |
| Windows x64 | `BandTabStudio-Windows-x64-Setup.exe`、`BandTabStudio-Windows-x64-Portable.zip` |
| macOS Apple Silicon | `BandTabStudio-Darwin-arm64.dmg` 和 `.zip` |
| macOS Intel | `BandTabStudio-Darwin-x86_64.dmg` 和 `.zip` |
| Linux x86_64 | `BandTabStudio-Linux-x86_64-glibc<构建机版本>.tar.gz` |

Mac 的 DMG 和 ZIP 是同一应用的两种分发方式，发布时可只选 DMG。Intel 与 Apple Silicon 分开构建；不能改名冒充另一种架构。当前 Mac 成品仍待构建与验证，签名、公证也需另行完成。README 只标注实际通过的状态。

参考：[GitHub 创建 Release](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)、[附件限制](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)。

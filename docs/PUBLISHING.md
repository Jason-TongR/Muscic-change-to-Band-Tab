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

## 3. 这一次 Release 填什么

建议先发布 Linux 预览版：

| 字段 | 建议填写 |
| --- | --- |
| Tag | `v0.2.0-preview.1` |
| Target | 包含这次桌面程序源码及文档的提交或分支 |
| Release title | `BandTab Studio v0.2.0-preview.1 · Linux 桌面预览版` |
| Description | 复制[已写好的发布说明](releases/v0.2.0-preview.1.md)全文 |
| This is a pre-release | 勾选，表示预览版本 |

这个 tag 是发布标签；当前应用内版本号为 0.2.0。如果该 tag 已被使用，选择新标签，不要用新包覆盖旧版标识。

进入仓库的 [Releases 页面](https://github.com/Jason-TongR/Muscic-change-to-Band-Tab/releases)，创建新 Release，填写标签、标题和说明，再上传下表文件。可以先保存草稿，检查附件后发布。[GitHub 创建 Release 说明](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)

### 这次要上传的三个文件

这些文件已在本地项目根目录的 `release/` 中生成：

| 文件 | 大小约值 | 作用 |
| --- | --- | --- |
| `BandTabStudio-Linux-x86_64-glibc2.43.tar.gz` | 489 MiB | 用户下载的完整 Linux 程序，包含运行库和模型 |
| `SHA256SUMS.json` | 119 B | 校验文件，目前记录上述 Linux 程序包的 SHA-256 |
| `原创练习曲.bandtab` | 1.3 MiB | 示例歌曲项目，包含音频和预先编写的谱子；不是软件 |

发布说明粘贴在 Release 的描述框中，无需把 Markdown 文件再作为附件上传。README 中已有界面截图，也不必作为下载附件重复上传。

GitHub 会自动提供 `Source code (zip)` 和 `Source code (tar.gz)`，不需要你再上传源码压缩包。这两个附件不能替代程序包。Release 单个附件需小于 2 GiB，当前 Linux 包符合该限制。[GitHub Releases 说明](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)

### 本次发布说明应保留的兼容范围

- 仅提供 Linux x86_64 成品包，构建环境为 Ubuntu 26.04 / glibc 2.43。
- Windows、Mac 尚无经过验证的成品包，不要写成已经发布三平台安装包。
- 当前测试验证了离屏界面、文件流程和模型推理，没有验证实体扬声器播放。
- 识别结果仍需人工复核，示例曲不作为准确率证明。

## 4. 后续如何补齐 Windows 和 Mac

1. 将源码和 `.github/workflows/desktop-build.yml` 推送到 GitHub 默认分支。
2. 进入仓库 Actions，找到 **Build desktop applications**，手动运行 **Run workflow**。
3. 等相应平台的构建和自检任务成功，下载其 Actions artifact。
4. 解压 artifact，取其中 `release/` 里的成品文件；不要把 Actions artifact 外层 ZIP 直接当安装包发布。
5. 在对应系统检查实际启动与音频播放，再上传对应版本的 Release，并更新 README 的平台状态。

当前工作流只构建、测试并保存产物，不自动发布 Release。各平台任务独立执行，一种平台通过不代表其他平台也通过。

按当前构建脚本，成功构建后可获得：

| 平台 | 成品附件 |
| --- | --- |
| Windows x64 | `BandTabStudio-Windows-AMD64.zip`；构建环境装有 Inno Setup 时另有 `BandTabStudio-Windows-x64-Setup.exe` |
| macOS Apple Silicon | `BandTabStudio-Darwin-arm64.dmg` 和 `.zip` |
| macOS Intel | `BandTabStudio-Darwin-x86_64.dmg` 和 `.zip` |
| Linux x86_64 | `BandTabStudio-Linux-x86_64-glibc<构建机版本>.tar.gz` |

Mac 的 DMG 和 ZIP 是同一应用的两种分发方式，可以只上传 DMG。Intel 与 Apple Silicon 必须分清架构，不能只改文件名当作另一种架构的程序。

每个平台会生成自己的 `SHA256SUMS.json`。合并多个平台发布时，把各包记录合并到一个文件，或分别重命名为带平台名的校验文件，避免同名覆盖；只保留本次实际上传附件的校验记录。

Windows/Mac 上传后，再把 README 中对应平台的「尚未提供」改为实际验证状态。对于已经发布且禁止修改附件的版本，创建新的 Release。

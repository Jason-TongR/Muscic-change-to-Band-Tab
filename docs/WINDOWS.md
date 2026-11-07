# Windows 桌面版

[返回 README](../README.md)

## 使用者下载什么

目标系统为 Windows 10 1809 及以上、Windows 11 的 x64 电脑。选择经过 Windows 构建与安装验证的版本；不提供 Windows 7、32 位或原生 ARM64 包。

| 文件 | 适合谁 | 启动方式 |
| --- | --- | --- |
| `BandTabStudio-Windows-x64-Setup.exe` | 希望有安装向导、快捷方式和卸载入口 | 双击安装，随后从开始菜单打开 |
| `BandTabStudio-Windows-x64-Portable.zip` | 希望解压使用 | 完整解压，双击目录中的 `BandTabStudio.exe` |
| `原创练习曲.bandtab` | 想先体验跟谱与编辑 | 在程序里使用「打开分享项目…」导入 |
| `SHA256SUMS.json` | 核对程序包及示例项目下载是否完整 | 比对对应文件的 SHA-256 |

安装版和便携版都包含 CPU 识别引擎、运行库、音频解码器及模型，不需要使用者安装 Python。便携版也需要保留 `_internal` 等完整目录。

安装向导支持简体中文和英文，默认按当前用户安装，无需管理员权限。可选桌面快捷方式及 `.bandtab` 的「打开方式」注册；不会强行替换其他软件的默认文件关联。需要时在 Windows「打开方式」中选择 BandTab 并设为默认。

曲库默认位于 `%LOCALAPPDATA%\BandTab Studio\`，与软件安装目录分开。重复安装用于更新程序，卸载保留曲库；重要歌曲可用 `.bandtab` 另行备份。

## 开发者一键构建

在 Windows x64 上安装 Python 3.11 x64 和 Inno Setup 6.5 及以上，然后在工程根目录运行 `build-windows.cmd`。构建器需要 Inno Setup 自带的 `Languages/ChineseSimplified.isl`；找不到编译器时可以用环境变量 `ISCC` 指向完整的 `ISCC.exe` 路径。

它依次执行：

1. 创建 `.venv-desktop` 并安装 GUI、CPU AI 和打包依赖。
2. 运行自动测试。
3. 打包 EXE、完整便携 ZIP 和中文安装程序，并生成原创示例与校验文件。
4. 从含中文和空格的目录解压、运行便携 EXE。
5. 静默安装到临时目录，验证开始菜单快捷方式和项目打开命令。
6. 运行安装后的真实六轨 AI 转写，再检查重复安装和卸载是否保留用户数据。

已有开发环境时，可以在 PowerShell 执行：

```powershell
./scripts/build_windows.ps1 -SkipSetup
```

**安装验证应在干净的构建机上执行。** 如果检测到已有 BandTab 安装，验证脚本会停止，以免测试覆盖正在使用的软件。只需要构建、不在当前电脑试装时，运行：

```powershell
./.venv-desktop/Scripts/python.exe scripts/build_desktop.py --archive --require-installer
```

PowerShell 若按本机策略禁止脚本运行，可在允许运行脚本的构建环境执行；不需要为普通使用者更改系统策略。

## GitHub Actions 构建

[Build Windows installer](../.github/workflows/windows-build.yml) 使用 Windows Server 2022 x64 构建机。主分支或 `codex/windows-*` 分支的相关源码变更会触发，也可以手动运行。工作流不会自动发布 Release。

- 成功产物：`BandTabStudio-Windows-x64` artifact，包含 `release/` 中的软件、示例、校验值、构建信息及验证报告。
- 诊断产物：`BandTabStudio-Windows-diagnostics`，包含程序截图、测试报告、安装和识别日志。
- 下载 Actions artifact 后先解压外层 ZIP，取出真正的安装 EXE / Portable ZIP 再发布。

验证过程清除开发环境的 Python 路径和模型目录，使用打包程序自己的依赖；指定离线模型模式，缺模型会失败而不是联网补下载。测试也会确认主程序是 x64 Windows PE 文件，并加载 Windows Qt 平台插件。

## 验证范围与限制

以对应构建的 `Windows-validation.json` 中 `status: pass` 为准。Linux 上通过的测试不等于 Windows 安装验证通过。Windows 构建机上的界面和模型检查也不能代替真实电脑上的扬声器、耳机及不同驱动测试。

预览包可能未签名；版本说明会标明签名情况。发布附件应保留随包第三方组件声明。识别精度与其他平台相同，失真、叠录、特殊奏法、鼓点和重拍仍需人工复核。

平台目标依据：[Qt 6.11 Windows 支持配置](https://doc.qt.io/qtforpython-6.11/overviews/qtdoc-windows.html)。安装验证采用 [Inno Setup 官方命令行参数](https://jrsoftware.org/ishelp/topic_setupcmdline.htm)。

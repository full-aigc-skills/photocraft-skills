# PhotoCraft 独立技能

当前正在实现，尚未完成插件发布验收。

`photocraft-use` 自带 Python 3.11+ 安装器，固定官方 macOS arm64 CLI 制品，校验压缩包和二进制，保留许可证，原子安装新版本，复用完整的已有版本。技能目录可独立复制，不依赖兄弟技能或插件私有路径。

运行测试：`python3 -m unittest discover -s tests -v`。完整创作流程和宿主验收仍待完成。

规范和任务：[PhotoCraft 插件 OpenSpec](https://github.com/full-aigc-plugins/photocraft-plugin/tree/main/openspec/changes/establish-v1-plugin)。

[English](README.md)

独立技能现已提供受限目录内的原生工作流助手，覆盖像素素材、可编辑文字、蒙版、原生/PSD 导出和独立尺寸变体。真实测试验证了保护区域，以及合成样例的 PSD 往返像素一致性。插件 Harness 与宿主验收仍待完成。

# PhotoCraft 独立技能

当前正在实现，尚未完成插件发布验收。

`photocraft-use` 自带 Python 3.11+ 安装器，固定官方 macOS arm64 CLI 制品，校验压缩包和二进制，保留许可证，原子安装新版本，复用完整的已有版本。技能目录可独立复制，不依赖兄弟技能或插件私有路径。

运行测试：`python3 -m unittest discover -s tests -v`。完整创作流程和宿主验收仍待完成。

规范和任务：[PhotoCraft 插件 OpenSpec](https://github.com/full-aigc-plugins/photocraft-plugin/tree/main/openspec/changes/establish-v1-plugin)。

[English](README.md)

独立技能现已提供受限目录内的原生工作流助手，覆盖像素素材、可编辑文字、蒙版、原生/PSD 导出和独立尺寸变体。真实测试验证了保护区域，以及合成样例的 PSD 往返像素一致性。插件 Harness 与宿主验收仍待完成。

开发版本 `0.1.0-dev.1` 修复并行首次安装/复用时的安装锁竞争：等待最多 120 秒，再核验复用；超时不覆盖安装或重放编辑任务。

开发版本 dev.2 的原生交付包含摘要绑定的 exchange-loss.json，区分格式损失、结构观察与未验证字体/效果保真；导出派生物不替代原生工程。

## CLI 与场景技能体系

[PhotoCraft Skill Suite Architecture](docs/PhotoCraft-Skill-Suite-Architecture.zh_CN.md)

| 技能 | 用途 |
| :--- | :--- |
| `photocraft-use` | 组合多个本工具能力并保留可编辑原生交付 |
| `photocraft-cli` | 查询实际命令参数和能力，调用公开 CLI、MCP 与诊断 |
| `photocraft-cli-setup` | 首次安装、摘要校验、版本检查与缺失运行时排障 |
| `photocraft-cli-project` | 创建、打开和保存 pcraft，检查尺寸、深度和色彩模式 |
| `photocraft-cli-layers` | 组织产品、背景、文本与图层组，调整混合和层级 |
| `photocraft-cli-selection` | 创建选区、反选、羽化和局部选择 |
| `photocraft-cli-masks` | 建立图层蒙版、矢量蒙版与剪贴合成 |
| `photocraft-cli-adjustments` | 使用调整图层或指定局部颜色调整 |
| `photocraft-cli-retouch` | 对已授权图像做修复、克隆、画笔和局部修饰 |
| `photocraft-cli-text` | 创建和修改文字图层、字体、段落和布局 |
| `photocraft-cli-resize` | 调整画布和图像尺寸，制作海报封面变体 |
| `photocraft-cli-export` | 从原生图层工程输出 PSD、PNG 或其他交换文件 |

`npx skills add full-aigc-skills/photocraft-skills --skill <skill-name>`

命令统一使用 `SKILL_DIR`，其值为宿主实际加载的 `SKILL.md` 所在绝对目录。支持用户级、项目级 `.agents/skills` 及插件内部或缓存目录；CLI 运行时另外安装到用户数据目录。每个技能单独复制到三种含空格的布局后，文档中的脚本入口均可运行 `--help`。[路径验证](docs/evidence/installed-skill-paths.json)。既有宿主缓存需更新后才会收到修正文档。

# PhotoCraft 独立技能

当前固定版本协议故障首用复验通过：48个独立技能源共288例，实际安装副本24例及四领域健康返工通过；58项安装摘要保持一致。验收范围与固定标签见 [协议故障验收记录](docs/evidence/codex-protocol-fault-first-use-20261007.json)。全量逐命令／GUI验收以及Art领域包升级仍开放。

协议故障修复候选：本领域12项技能逐个单独复制、空运行时公开安装后，原生保存成功再注入六种坏回复全部通过（72例，零跳过）。不重放、未知回执、工程重开与交付／技能保全均已检查。[证据](docs/evidence/protocol-fault-first-use-20261007.json)。固定安装副本与Art领域包升级仍为独立门禁。

固定插件 0.1.0-dev.13／技能源 0.1.0-dev.12 已通过安装后的返工门禁：隔离 Codex 发现全部58项技能零加载错误，本领域安装技能从空运行时直接执行文档创建／返工计划、保存重开与非目标保全。全部58项安装摘要不变，当前固定发行CI通过。[固定返工证据](docs/evidence/codex-complete-command-revision-first-use-20261007.json)。全量命令／GUI／模型验收保持开放。

本领域 12 个技能逐个单独复制、从各自空运行时公开安装后，配套返工计划全部通过（62.759 秒，零跳过）。[返工证据](docs/evidence/complete-command-revision-first-use-20261007.json)。更新快照的真实固定宿主安装另设门禁。

完整命令入口补充了配套的创建／返工 JSON 示例、重新打开后的显式选择前置条件，以及原生保存重开、非目标对象与像素检查。每个独立技能均包含两个可执行计划。[调用指南](skills/photocraft-use/references/command-usage.md#7-可执行局部返工--executable-targeted-revision)。全量逐命令及 GUI 验收保持开放。

先前固定 Codex 快照首用通过：五插件／58 技能发现、58 项安装技能分别空运行时公开安装、四领域完整命令代表样例、Art HD 返工／恢复／移动包、安装摘要保全与固定发行 CI。[证据](docs/evidence/codex-complete-command-first-use-20261007.json)。这是有范围的原生验收；通用 Skills CLI 安装和全命令／GUI 验收仍开放。

## 完整原生命令入口

全部 12 项独立技能分别从空运行时使用公开锁定 CLI 附件安装，随后完成创建、保存重开、领域参数及渲染检查（74.187 秒，零跳过）。[逐技能冷首用证据](docs/evidence/complete-commands-cold-first-use-20261007.json)。本轮覆盖每项技能的完整命令代表样例；全命令／GUI 和实际宿主安装另行验收。

已发布开发快照：skills dev.11 / plugin dev.12；固定宿主首用代表门禁通过。

748 条命令现在均有逐项参数说明、技能归属与同会话调用入口。运行 `commands.py list / describe / check / run`；原生状态按实时 enabled 校验。旧工作流的 32 项交付合同保留。GUI 命令需显式 bridge，命令目录覆盖不代表全量验收。

[架构与操作指南](docs/PhotoCraft-Complete-Commands-Architecture.zh_CN.md) · [逐项参考](skills/photocraft-use/references/command-reference.md) · [可运行示例](skills/photocraft-use/examples/commands-advanced.json)

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

dev.5 补齐局部调整的选区/蒙版前置、修图的目标图层选择及画笔/克隆/修复数值范围。九类场景均只复制当前技能并冷安装，完成真实原生编辑、结构和像素核验；完整回归 36 项、零跳过。[证据](docs/evidence/task-skill-first-use.json)。此证据不覆盖全部 748 命令、复杂纹理修复质量或 GUI/模型派发。

固定插件 dev.6／技能 dev.5 的实际安装单文字技能中文海报冷启动与标题修订通过（1 项，5.927 秒）。源文件和保护区域不变，PSD 保留文字且解码像素与 PNG 一致；未知图层和缺失字体被拒绝。人工接受仍为 NOT_RUN。[架构](docs/PhotoCraft-Chinese-Text-Architecture.zh_CN.md)、[证据](docs/evidence/chinese-text-first-use.json)。

源候选 dev.6 为源工程局部修改增加 protectedRegions。真实失败测试复现旧流程把保护区改动发布为成功；修复后发布前拒绝并保留源文件。全量 44 项通过、0 跳过，系统 Python 单技能在线验收通过；固定插件验收尚待完成。[架构](docs/PhotoCraft-Protected-Region-Architecture.zh_CN.md)、[证据](docs/evidence/protected-regions-first-use.json)。

固定 PhotoCraft 插件 dev.7／技能 dev.6 与 ArtCraft 插件 dev.30／技能 dev.26 的实际安装原生保护／交接复验通过；五插件全部 58 个技能摘要不变。只完成对应保护任务，整体实现和创作接受仍未完成。[证据](docs/evidence/codex-release30-protected-native-20261006.json)。

源码候选：PhotoCraft 公开工作流已接通笔刷、仿制图章和修复笔刷，并支持显式保护区域。单技能全新在线原生安装测试通过；固定发布、插件快照更新和安装后复验尚待完成。参见[有界源码证据](docs/evidence/retouch-workflow-first-use.json)。

固定 PhotoCraft 插件 dev.8／技能源 dev.7 与 ArtCraft 插件 dev.31／技能源 dev.27 通过安装后的原生修图和交接测试（13.260 秒／23.264 秒）。58 个安装后技能摘要全部保持不变。仅完成有界修图任务；完整目标仍未完成。[证据](docs/evidence/codex-release31-retouch-native-20261006.json)。

尺寸变体增量 / Layout variants: source-bound crop, padding and resampling records, editable role identities, and final-canvas safe-area gates. See `docs/PhotoCraft-Layout-Variant-Architecture.md` and `docs/PhotoCraft-Layout-Variant-Architecture.zh_CN.md`. Native runtime remains 0.2.0; skills development version is 0.1.0-dev.8.

固定已安装插件 dev.9／技能源 dev.8 的补充首次使用验收验证分层蒙版海报、改字与封面，并用 Pillow 独立核对三份不透明 PSD 合成图与 PNG 全部 RGB 像素；这与原生图层检查分开，不代表 Photoshop 实际编辑验收。[验收记录](docs/PhotoCraft-Independent-PSD-Acceptance.zh_CN.md)。

纯图片工作流字体前置条件：[架构](docs/PhotoCraft-Font-Preconditions-Architecture.zh_CN.md)。技能源 dev.9 候选通过公开冷启动原生创建／修订与独立 PNG／PSD 检查；固定插件实际安装复验仍待完成。

固定插件 dev.10／技能源 dev.9 通过实际 Codex 0.153.4 安装及单技能纯图片冷启动原生验收（5.601 秒）；58 个已发现安装技能摘要全部不变。升级后的 ArtCraft 固定混合验收单独执行。[证据](docs/evidence/codex-photo10-fontless-first-use-20261006.json)。

固定已安装矩阵 Film9／Effect8／Photo10／Vector11／Art61 通过登记 PNG／JPEG 的 Vector→Photo 替换复用（1 项）、四领域原生首用／恢复／打包（3 项），以及更新的 Photo／Art 全部 22 技能独立空缓存 CLI 检查（190.051 秒）；58 个安装技能摘要保持不变。SVG 混合输入、动态透明序列与完整创作验收仍开放。[证据](docs/evidence/codex-release61-vector-photo-first-use-20261006.json)。

技能源 `0.1.0-dev.10` 固定维护版 CLI `0.2.0-craft.1`，登记智能对象放置、替换与重新链接收集保持嵌入式可编辑内容、变换和蒙版。单技能公开下载冷首用通过；实际固定插件安装及 Art 混合验收待执行。[证据](docs/evidence/smart-public-source-first-use-20261006.json)。

固定 Photo 插件 dev.11／技能源 dev.10／维护版 CLI 0.2.0-craft.1 已通过安装副本单技能智能对象放置／替换／重新链接收集与移动修订（4.633 秒）、PSD 独立解码及纯图片回归两项、十二项独立冷启动（51.647 秒）、全部 58 安装摘要、公开附件及四项标签 CI。默认维护版安装与旧官方 0.2.0 并存，旧二进制不变。[版本证据](docs/evidence/codex-photocraft11-smart-first-use-20261006.json)。Art 混合升级已按下述版本验收；完整首版仍开放。

2026-10-06 固定智能对象混合验收：Art 插件 dev.70／技能源 dev.47／运行时 dev.68 与 Photo 插件 dev.11／技能源 dev.10／维护版 CLI 0.2.0-craft.1，通过安装后原生测试一项（64.957 秒）、十项 Art 独立冷启动、58 安装摘要保全、五固定包重建及四项对应提交 CI。Logo 替换保留海报智能对象变换、蒙版及非目标图层；受影响 Logo／海报／片头／影片更新，独立任务复用，成片十二帧独立解码、坏帧恢复及五子工程移动验包通过。[证据](docs/evidence/codex-artcraft70-smart-mixed-first-use-20261006.json)。完整首版、通用 Skills CLI、GUI／模型调度、持久外部链接及外部 PSD 保真仍开放。

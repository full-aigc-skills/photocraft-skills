# PhotoCraft Droplet 监督候选

技能源dev.43打包craft.5内部droplet监督候选，插件dev.49锁定这些模块。公开cli.py仍使用craft.1锁，craft.5原生运行时未启用、未做固定安装验收。

普通执行与监督执行共用原引擎droplet解析和计划准备；监督路径保留相同read_file、import、临时Session、动作命令与save_doc，保留引擎0–12 JPEG质量标度、options／CLI输出优先级、格式规范化、文件／目录输入顺序和重复输入。普通droplet仍收集逐文件错误并继续。

只读计划帧在打开文档或创建输出前绑定规范化动作及每个输入／目标。打开、动作、保存各自严格核验并确认，任一未知回复或原生失败立即停止整个监督批次。保存后故障保留真实产物和unknown请求回执，后续文件不动，不重放编辑。健康输出保持原有ok目标路径格式。

复现：scripts/build_smart_runtime.py使用--manifest supervised-droplet-patch.json --version 0.2.0-craft.5；执行runtime/tests时设置CRAFT_SUPERVISED_BINARY为构建出的二进制，CRAFT_SUPERVISED_VERSION=0.2.0-craft.5。research只读，补丁在固定上游的临时副本中应用。

验证证据在插件supervised-droplet目录记录。流式、嵌套聚合命令内部步骤、公开CLI／运行时来源接入、持久恢复及候选固定安装仍开放；不能据局部候选关闭任务9.6。

40项定向测试零跳过、58项Rust测试通过。质量变更红灯来自真实原生保存后才拒绝；修复后计划绑定质量，绿灯仅出现序号1且零确认、零输出。JPEG字节与尺寸对比公开craft.1一致；六类真实保存后故障保全原输入及重开产物。完整源回归在插件证据另记。

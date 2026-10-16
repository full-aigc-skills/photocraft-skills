# PhotoCraft mask-local 场景

以下坐标以256×192单一栅格原图为例。先读取尺寸、图层和当前命令schema；依据输入重算轮廓与采样位置。原图含活动路径时先退出路径编辑，避免调整层错误使用矢量蒙版。

## window-highlight-local：室内窗景局部压高光

输入：窗外仍有真实纹理，窗框可定位；矩形应落在窗内，不跨入室内。

| 顺序与目的 | Craft 命令 | 参数示例 |
| --- | --- | --- |
| 1. 从单一栅格原图复制工作层；当前无活动路径，已有选区先取消 | `select.deselect` | `{}` |
| 2. 保留原始像素，复制并激活工作层 | `layer.duplicate` | `{"name":"Window highlight"}` |
| 3. 按实际目标轮廓定位；此处为256×192测试矩形 | `select.rect` | `{"x":144,"y":16,"width":80,"height":100,"mode":"replace","feather":2}` |
| 4. 以窗选区创建可编辑曲线蒙版，降低中高光 | `layer.newAdjustmentLayer.curves` | `{"points":[[0,0],[128,108],[220,200],[255,255]]}` |
| 5. 结束局部操作，清除活动选区 | `select.deselect` | `{}` |

检查：室内未选区RGB保持不变；窗框没有暗晕；曲线层与其蒙版保存。

边界：纯白剪切区没有可恢复细节；无法用压暗创造窗外景物。

## portrait-subject-lift：人物面部局部提亮

输入：人工确认脸部区域，保留额头已有高光；示例矩形须按实际脸形改为套索。

| 顺序与目的 | Craft 命令 | 参数示例 |
| --- | --- | --- |
| 1. 从单一栅格原图复制工作层；当前无活动路径，已有选区先取消 | `select.deselect` | `{}` |
| 2. 保留原始像素，复制并激活工作层 | `layer.duplicate` | `{"name":"Face lift"}` |
| 3. 按实际目标轮廓定位；此处为256×192测试矩形 | `select.rect` | `{"x":80,"y":48,"width":64,"height":64,"mode":"replace","feather":5}` |
| 4. 选区作为调整层蒙版，只抬中间调 | `layer.newAdjustmentLayer.levels` | `{"gamma":1.15}` |
| 5. 结束局部操作，清除活动选区 | `select.deselect` | `{}` |

检查：脸部可见提亮；四角背景与原图一致；没有扩大脸型或改动五官。

边界：低光噪声随提亮增强；只做曝光整理，不声称重建人脸。

## background-desaturate-focus：保留商品颜色并弱化背景色

输入：商品轮廓能够人工勾选；矩形仅用于方形包装正面示例。

| 顺序与目的 | Craft 命令 | 参数示例 |
| --- | --- | --- |
| 1. 从单一栅格原图复制工作层；当前无活动路径，已有选区先取消 | `select.deselect` | `{}` |
| 2. 保留原始像素，复制并激活工作层 | `layer.duplicate` | `{"name":"Background quiet"}` |
| 3. 按实际目标轮廓定位；此处为256×192测试矩形 | `select.rect` | `{"x":64,"y":48,"width":128,"height":96,"mode":"replace","feather":0}` |
| 4. 反选到背景 | `select.inverse` | `{}` |
| 5. 轻柔过渡，避免轮廓外硬线 | `select.modify.feather` | `{"radius":1}` |
| 6. 仅降低背景饱和度，主体通过蒙版排除 | `layer.newAdjustmentLayer.hueSaturation` | `{"saturation":-55}` |
| 7. 结束局部操作，清除活动选区 | `select.deselect` | `{}` |

检查：主体中心RGB不变；背景仍保留明暗层次；边缘无漏色或灰边。

边界：透明、反光与毛发边缘需要额外手绘蒙版，矩形不能代替真实轮廓。

## background-soft-blur：主体外背景柔化

输入：主体与背景边界明确，不用于透明物体。

| 顺序与目的 | Craft 命令 | 参数示例 |
| --- | --- | --- |
| 1. 从单一栅格原图复制工作层；当前无活动路径，已有选区先取消 | `select.deselect` | `{}` |
| 2. 保留原始像素，复制并激活工作层 | `layer.duplicate` | `{"name":"Background blur"}` |
| 3. 按实际目标轮廓定位；此处为256×192测试矩形 | `select.rect` | `{"x":64,"y":48,"width":128,"height":96,"mode":"replace","feather":0}` |
| 4. 反选背景 | `select.inverse` | `{}` |
| 5. 在背景一侧形成过渡 | `select.modify.feather` | `{"radius":2}` |
| 6. 只模糊选区内像素 | `filter.blur.gaussianBlur` | `{"radius":3}` |
| 7. 结束局部操作，清除活动选区 | `select.deselect` | `{}` |

检查：主体中心纹理不变；背景细节减少；轮廓没有明显亮边。

边界：这是选择性高斯模糊，不等同真实镜头景深；重叠边缘可能出现光晕。

## garment-color-local：服装定向改色并保持肤色

输入：经授权修改服装色；先用套索标出衣物，不包含皮肤。

| 顺序与目的 | Craft 命令 | 参数示例 |
| --- | --- | --- |
| 1. 从单一栅格原图复制工作层；当前无活动路径，已有选区先取消 | `select.deselect` | `{}` |
| 2. 保留原始像素，复制并激活工作层 | `layer.duplicate` | `{"name":"Garment color"}` |
| 3. 用衣物轮廓建选区，坐标需现场测量 | `select.lasso` | `{"points":[[72,92],[144,92],[164,172],[52,172]],"mode":"replace","feather":1}` |
| 4. 调整层仅改选中衣物的色相 | `layer.newAdjustmentLayer.hueSaturation` | `{"hue":25,"saturation":-5}` |
| 5. 结束局部操作，清除活动选区 | `select.deselect` | `{}` |

检查：皮肤与背景不变；衣物褶皱亮度仍连续；颜色符合目标样品。

边界：此例不是精确实物色校准；中性黑白衣物仅旋转色相可能无效。

## white-product-local-neutral：白色包装局部去黄

输入：白色包装区域有可观察黄色偏色，保留环境暖光。

| 顺序与目的 | Craft 命令 | 参数示例 |
| --- | --- | --- |
| 1. 从单一栅格原图复制工作层；当前无活动路径，已有选区先取消 | `select.deselect` | `{}` |
| 2. 保留原始像素，复制并激活工作层 | `layer.duplicate` | `{"name":"Neutral label"}` |
| 3. 按实际目标轮廓定位；此处为256×192测试矩形 | `select.rect` | `{"x":88,"y":68,"width":72,"height":48,"mode":"replace","feather":1}` |
| 4. 在包装选区内降低黄通道饱和度 | `layer.newAdjustmentLayer.hueSaturation` | `{"yellows":{"saturation":-35}}` |
| 5. 结束局部操作，清除活动选区 | `select.deselect` | `{}` |

检查：周围暖色背景保持；白标仍有折痕层次；品牌原本黄色没有被误选。

边界：必须先确认此区域应为中性白，不能把产品固有黄色当色偏。

## sky-gradient-balance：天空与地面渐变曝光平衡

输入：天空偏亮但未剪切，地平线无遮挡；例子假设天空在上半部。

| 顺序与目的 | Craft 命令 | 参数示例 |
| --- | --- | --- |
| 1. 从单一栅格原图复制工作层；当前无活动路径，已有选区先取消 | `select.deselect` | `{}` |
| 2. 保留原始像素，复制并激活工作层 | `layer.duplicate` | `{"name":"Sky gradient"}` |
| 3. 先建整体压亮曲线；随后立即将蒙版限定到上方 | `layer.newAdjustmentLayer.curves` | `{"points":[[0,0],[128,105],[255,240]]}` |
| 4. 在调整层蒙版从上白到下黑，地面恢复原曝光 | `paint.gradient` | `{"target":"mask","from":[128,40],"to":[128,112],"colors":["#ffffff","#000000"],"opacity":100}` |
| 5. 结束局部操作，清除活动选区 | `select.deselect` | `{}` |

检查：天空层次增加；地面下方曝光不变；地平线过渡平滑。

边界：树枝或建筑穿过地平线时需补画蒙版；纯白天空不可恢复。

## corner-vignette-mask：柔和暗角突出画面中心

输入：用户希望轻度暗角；主体处于中央，四角没有需保留的文字。

| 顺序与目的 | Craft 命令 | 参数示例 |
| --- | --- | --- |
| 1. 从单一栅格原图复制工作层；当前无活动路径，已有选区先取消 | `select.deselect` | `{}` |
| 2. 保留原始像素，复制并激活工作层 | `layer.duplicate` | `{"name":"Vignette"}` |
| 3. 建立中央椭圆保护区 | `select.rect` | `{"x":40,"y":24,"width":176,"height":144,"ellipse":true,"mode":"replace"}` |
| 4. 反选到画面边缘 | `select.inverse` | `{}` |
| 5. 大半径羽化形成渐变 | `select.modify.feather` | `{"radius":20}` |
| 6. 仅压暗外围中间调 | `layer.newAdjustmentLayer.levels` | `{"gamma":0.88}` |
| 7. 结束局部操作，清除活动选区 | `select.deselect` | `{}` |

检查：中心亮度基本保持；四角过渡平滑；没有明显椭圆框。

边界：不用于证据照片或要求均匀照度的商品标准图；按主体位置重算椭圆。


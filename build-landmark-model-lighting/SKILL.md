---
name: build-landmark-model-lighting
description: 调研并重建真实建筑与地标：整理用户和公开素材，只用 Codex 宿主 image_gen.imagegen 生成可追溯方向图，构建语义化 GLB 与 Three.js 交互预览，适配扫描上色、结构生长或拓扑寻光，并用同一轮证据封印验证真实资产、运行时和浏览器结果。用于按图片或公开资料建模、制作建筑白模或地标 3D 资产、添加光效、交付 GLB/WebGL 页面、审计旧模型或排查“脚本通过但模型/证据未闭环”时。
---

# 地标建模与光效

## 核心原则

- 严格按“调研素材 → 冻结简报 → 内置生图 → 白模建模 → 白模校对 → 材质与光效 → 机器候选 → 按需双源终验”推进。
- 让真实资料决定身份、尺度、轮廓、结构和隐藏面；只让生成图决定构图、材质气质和光效语言。
- 先修主体，再修展示。不得用材质、发光、镜头或控制壳掩盖比例和结构错误。
- 每个模型至少实现一种合适光效；内置三类能力不等于每个主体强制交付三类。
- 把交付分为 `candidate-ready` 与 `visual-approved`：前者证明当前字节、结构和运行时可复现，后者才证明视觉身份已由用户或明确授权的 Reviewer 接受。不得把前者写成后者。
- 默认 `review_mode=user-self-check`：运行必要的自动化检查，交付绝对路径、URL 和人工验收动作；除非用户明确要求截图/视觉验收，不主动生成成套截图或做耗时主观复核。
- 任何 `passed` 都必须绑定可解析的真实 GLB/图片、当前源码/运行时哈希、本轮报告和 HTTP 返回字节；自报布尔值、HTTP 200、单张截图或旧报告都不是证据。
- 把时间连续性当作独立门禁：`0 / mid / 1` 单帧正确不等于动效正确；暂停、回放、模式切换、后台恢复和画廊交换都必须通过连续帧验收。

## 项目规则优先级

- 进入工作区后先读取当前目录及其父级适用的 `AGENTS.md`；它是项目交付契约，优先级高于本 Skill 的通用默认值。
- 在 `form-atlas` 中，根目录 `AGENTS.md` 对展示壳、模型、材质、光效和验收拥有最终解释权。本 Skill 的引用文件必须与其保持一致；发现冲突时先按 `AGENTS.md` 执行并修正文档，不得自行选择较宽松的规则。
- `form-atlas` 的硬约束包括：loading 位于当前 3D 视口正中心且同一视口最多一个可见实例；loading 只在资产指纹/结构校验和真实首帧完成后隐藏，错误态先隐藏 loading；播放条固定底部居中；静态页与 React 页使用 `data-landmark-loading`、`.landmark-loading-ring` 和 `data-landmark-playback`；静态页优先复用 `public/white-models/shared/presentation-shell.css`，React 页复用 `app/globals.css`；桌面 `1440×900` 与移动 `390×844` 都要验收。
- 集成画廊不得重复注入 loading，也不得留下旧 iframe/WebGL 残影。平安金融中心按项目契约交付 `color / build / edge-color` 三种模式，`build` 主体动画为 4.8 秒。
- 保护已有未提交工作，只修改当前地标或共用展示壳；不得用一个地标的修复覆盖另一个地标的模型、材料或动效实现。

## 开始前

1. 检查目标工作区的 `AGENTS.md`、Git 状态、已有 3D 入口、依赖和等效运行进程。
2. 记录任务开始时间、目标版本、允许范围、禁止事项、验证方式、视觉复核模式和停止条件。默认视觉复核模式为 `user-self-check`。
3. 保护用户未提交改动。只修改任务相关目录；没有现有 3D 栈时才创建独立 Node ESM + Three.js 工程。
4. 使用下面的命令初始化交付合同。不得用 `--force` 或覆盖已有合同：

```bash
python3 <skill-dir>/scripts/init_case.py \
  --root <case-root> \
  --subject "<建筑名称>" \
  --slug <subject-slug> \
  --effect auto \
  --review-mode user-self-check
```

完整阶段门禁和数据合同见 [workflow.md](references/workflow.md)。

在 `form-atlas` 中，`--effect auto` 只用于初始化；平安金融中心进入严格交付前必须将 `selected_effects` 冻结为 `color / build / edge-color`，不得以 `auto` 作为最终交付值。

## 1. 调研并冻结参考

1. 先登记用户提供的图片、视频、图纸、网页、GLB 或尺寸。
2. 对真实建筑补齐 `front / back / left / right / roof / ground-contact / three-quarter`；优先业主、建筑师、工程团队、政府和权威档案。
3. 为每个来源记录 ID、机构、日期、定位信息、用途、视角、可信度、使用边界、本地路径和 SHA-256（如有本地文件）。不要把第三方图片打包进交付，除非授权明确。
4. 冻结 `ReferenceBundle` 和 `ModelBrief`。尺寸、主体版本、地标特征或关键结构证据不足时停止，不得用生图补造事实。

## 2. 只用 Codex 宿主内置生图

1. 直接调用 `image_gen.imagegen`；永远不要加载、安装或调用任何图片生成 Skill、Ark、豆包、Gemini、CLI、本地模型或第三方 API。
2. 生成全新图片时不要传参考图片参数；使用本地素材时传 `referenced_image_paths`；素材只存在于对话时，用最小的 `num_last_images_to_include` 覆盖目标图片。编辑本地图片前先用 `view_image` 检查。
3. 先生成 `white-idle` 母版，再基于同一母版编辑出每个已选光效的 `<effect>-mid` 和 `final-real-material`。锁定主体、机位、裁切、地面接触和背景。
4. 在 `DirectionSet` 中保存提示词、来源 ID、生成时间、路径和哈希，并明确 `structure_truth=false`。
5. 对照素材自检方向图。无重大冲突时继续；方向图改变真实尺度、轮廓或隐藏结构时先修图。内置图片工具不可用或失败时停止并报告，不得回退。

## 3. 建模并先验收白模

1. 以确定性源码生成或维护模型；优先复用现有工程栈，不引入与任务无关的框架。
2. 使用米制、Y-up、主体落地中心原点。建立可读的语义层级、材质区域、局部轴、完整 bounds 和地标点。
3. 依次完成 `blockout → macro → meso → micro`。每一级都执行 `state-sample → compare → find → revise → resample`，覆盖所有必需视角；默认保存结构化状态，用户明确要求视觉验收时才落盘 raster capture。
4. 保持暖白诊断材质，先检查轮廓、体量、开口、屋顶、立面、落地、背面和常用三分之四视角。
5. 白模没有通过真实参考与方向母版的同视口校对前，不得进入材质和光效。

## 4. 添加真实材质与至少一种光效

1. 从证据映射真实材质区域；未知材质使用中性黏土色并记录，不得猜成品牌色。
2. 按结构自动选型：
   - 有完整可追溯桁架、网格或骨架图时优先 `edge-color`。
   - 竖向装配、层级或生长语义明确时优先 `build`。
   - 其余使用通用默认 `color`。
3. 允许交付多种光效，但每种都必须独立通过门禁。不得为凑数量把 `edge-color` 退化成扫高光带。
4. 复用品牌页面色系和临时暖金光效；最终主体材质仍由真实资料决定。
5. 未给定时，`build` 主体段推荐 4–5 秒；这是可被项目证据和用户反馈覆盖的默认值，不是所有建筑的硬编码常量。
6. 在 `form-atlas` 中，平安金融中心的项目值覆盖通用默认值：必须交付 `color / build / edge-color`，其中 `build` 为 4.8 秒。
7. 所有自动运动共用一个时间源和一个循环 owner。暂停必须同时冻结 timeline、auto-rotate、damping、shader time、pulse 和局部光；replay 保留用户相机，并在首个已提交帧原子回到 0 状态。
8. 高频 shader 细节必须抗锯齿/降频；透明 overlay、细线和主体不得靠 `renderOrder` 解决共面深度竞争；切换前预热全部已选 shader variant。

读取 [visual-system.md](references/visual-system.md) 获取色板、三类光效特征、禁用模式、色彩空间和选择规则。
读取 [motion-stability.md](references/motion-stability.md) 获取 form-atlas 问题链、暂停/恢复语义、抗闪烁规则和连续帧测试矩阵。

## 5. 导出、运行与双源校验

1. 导出 GLB 2.0，绑定生成源码、资产 SHA-256、语义部件、几何统计和材质区域。
2. 提供带拖拽、缩放、暂停、重播、弱动态和所选光效的浏览器预览；实现 `window.__BUILD_WHITE_MODEL_MOTION_ACCEPTANCE__`，并遵循 [presentation-shell.md](references/presentation-shell.md) 及目标工作区 `AGENTS.md` 的 loading 与底部播放条约束。
3. 运行项目校验、构建/测试、Khronos 官方 glTF Validator 和真实 GLB loader；Validator 零 error 且项目检查通过才可继续。
4. 用自动化真实 Chromium/Chrome 验证 `1440×900` 与 `390×844`、七个标准视角、光效 `0 / mid / 1`、交互、失败恢复、loading 单实例/中心定位、画廊切换无旧 iframe/WebGL 残影和资源释放。默认只保存必要结构化报告；只有用户明确要求视觉验收时才生成并复核成套截图。
5. 执行连续帧矩阵：冻结基线、真实按钮暂停、replay 首帧、完整播放、全部模式对切换、hidden/visible 恢复、`0.98 / 0.99 / 1` 完成态和重复切换资源稳定性。不得用 acceptance bridge 的强制冻结代替真实暂停。
6. 分开比较：
   - 最终模型与真实素材：身份、尺度、结构、隐藏面和材质事实。
   - 最终运行时与生成图：构图、视觉层级、色系和光效语言。
7. `user-self-check` 模式输出七视角直达动作、失败信号和服务 URL，保持 `review_status=pending`；用户或明确授权 Reviewer 复核后，才记录差异、修复、复拍证据并把状态改为 `visual-approved`。

每次最终验证前先读取 [evidence-integrity.md](references/evidence-integrity.md)。GLB、建模源码、运行时、简报、来源或验证脚本任一变化，都必须作废旧封印并重新生成；不得手工把旧报告改成当前哈希。

完整接口、检查项和失败信号见 [acceptance.md](references/acceptance.md)。

## 交付前运行

```bash
python3 <skill-dir>/scripts/seal_evidence.py --root <case-root>
python3 <skill-dir>/scripts/validate_case.py --root <case-root> --strict
python3 <skill-creator-dir>/scripts/quick_validate.py <skill-dir>
```

只有用户明确要求并完成视觉复核时，再额外运行 `validate_case.py --strict --require-visual-approval`。旧 schema 只能用 `--allow-legacy-evidence` 做迁移诊断，不能据此宣称当前完整交付。

最终说明改了什么、如何验证、实际结果、当前是 `candidate-ready` 还是 `visual-approved`、仍有风险、人工验收步骤、运行 URL、提交哈希（如有）以及保留或清理的临时产物。停止本轮启动的服务器、浏览器和监听器。

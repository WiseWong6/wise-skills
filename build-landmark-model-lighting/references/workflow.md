# 地标建模工作流合同

## 目录

1. 完成定义与验收层级
2. 阶段状态机
3. ReferenceBundle
4. ModelBrief
5. DirectionSet
6. 建模迭代
7. DeliveryManifest 与 ComparisonReport
8. 阻塞与停止条件

## 1. 完成定义与验收层级

先冻结交付层级：

- 默认交付 `candidate-ready`：机器门禁全部通过，提供绝对路径、URL、准确操作和失败信号，等待用户自检。
- 用户明确要求截图/视觉验收时才进入 `agent-visual-review` 或 `independent-review`；七视角通过后标记 `visual-approved`。
- 只有 `visual-approved` 完成范围审计与清理后才标记 `delivered`。状态不能跨级外推。

`candidate-ready` 必须同时满足：

- 真实来源可追溯，七类视角被覆盖，关键尺寸或相对比例有依据。
- `ModelBrief.status` 为 `frozen`，目标版本、允许简化和禁止假设明确。
- 方向图由 `image_gen.imagegen` 直接生成，且没有被当作结构真值。
- GLB、确定性建模源码、交互运行时、方向图、关键帧和报告齐全。
- 至少一种光效通过开始态、中段、完成态和弱动态检查。
- 真实暂停、replay、连续播放、模式切换、后台恢复、完成态连续性和资源循环通过连续帧检查；不能只靠测试冻结态或最终截图。
- 最终资产、源码、运行时、三个报告和 HTTP 返回字节由同一 evidence seal 绑定。
- 真实浏览器中的主体、控件和交互可按交付步骤人工复现。

`visual-approved` 额外要求用户或明确授权 Reviewer 以当前资产哈希完成真实来源七视角复核。Builder 自报、单张 hero 图、旧截图或相似度分数都不能代替。

## 2. 阶段状态机

只允许按以下顺序推进：

`research → brief-frozen → direction-approved → blockout → macro → meso → micro → white-approved → material → lighting → final-qa → candidate-ready → visual-approved → delivered`

推进规则：

- `research`：允许新增、替换和降级来源，不允许开始最终几何。
- `brief-frozen`：把尺寸、地标点、部件和容差视为合同；修改时记录原因和版本。
- `direction-approved`：代理完成素材/方向自检；只有重大冲突或证据缺口才等待用户。
- `blockout` 到 `micro`：每一级先更新模型，再复拍同一组视角。
- `white-approved`：要求无材质和光效也能识别主体，且隐藏面、屋顶与落地成立。
- `material`：只应用有证据的区域；未知项保持中性并登记。
- `lighting`：从三类配方选择至少一种，不改变主体矩阵和构图合同；先完成单一时间源、原子状态提交、shader 预热和透明层深度策略。
- `final-qa`：锁定 GLB 哈希后完成浏览器、连续帧、光效和双源比较。
- `candidate-ready`：同轮封印与严格机器校验通过，等待用户自检；不得声称视觉已验收。
- `visual-approved`：用户或明确授权 Reviewer 留下绑定当前资产哈希的结果。

如果真实来源、ModelBrief、建模源码、最终 GLB、运行时或验证驱动任一变化，作废旧的 glTF/loader/browser 报告、视觉结论和 evidence seal，重新验证。

## 3. ReferenceBundle

为每个来源保存以下字段：

| 字段 | 要求 |
| --- | --- |
| `id` | 项目内唯一稳定 ID，如 `R01`、`M01`、`U01` |
| `source_type` | `fact`、`visual`、`drawing`、`material` 或 `user` |
| `authority_type` | `owner`、`architect`、`engineer`、`government`、`official`、`archive`、`publisher` 或 `user` |
| `authority` | 机构、作者或用户提供 |
| `locator` | URL、书目、文件路径或附件说明 |
| `published_at` | 已知日期；未知时为 `null` |
| `captured_at` | 本轮检索或接收时间 |
| `views` | 一个或多个标准视角；若来源覆盖全部方向则直接登记七项 |
| `supports` | 该来源实际支持的尺寸、部位或材质断言 |
| `rights` | 仅比对、可打包、用户授权等边界 |
| `confidence` | `high`、`medium` 或 `low` |
| `local_path` | 本地证据路径；没有则为 `null` |
| `sha256` | 有本地文件时必填 |

来源优先级：

1. 业主、设计/工程团队、政府和官方验收资料。
2. 权威档案、博物馆、学术出版和原始图纸。
3. 可定位作者和日期的专业摄影或媒体。
4. 无出处聚合图只作低置信度视觉线索，不支撑尺寸和隐藏面。

七类覆盖为 `front / back / left / right / roof / ground-contact / three-quarter`。一个 `all-axis` 来源可声明覆盖，但仍要在 `supports` 中说明实际包含内容。

## 4. ModelBrief

冻结以下内容：

- `subject.name`、`target_version`、`kind=architecture-or-landmark`。
- `required_features`：主体不可丢失的语义特征。
- `allowed_simplifications`：可省略的施工节点、室内、机电、环境等。
- `forbidden_assumptions`：至少声明生成图不作为尺寸或隐藏结构真值。
- `dimensions`：权威尺寸、来源 ID、单位和容差。
- `landmarks`：开口、转折、檐口、塔冠、支撑数量等视觉锚点。
- `required_parts` 和语义层级。
- `local_axes`、原点、坐标制和必需视角。
- `material_regions`：证据 ID、base color、roughness、metalness 和置信度。
- `selected_effects`：冻结前可为 `auto`，严格交付时必须是具体模式。
- `viewport_profiles`：至少桌面和紧凑视口。
- `motion_contract`：单一时间源、唯一循环 owner、用户暂停覆盖的自主运动源、replay 原子性、visibility 恢复语义、模式预热和画廊交换策略。
- `accuracy_class=visual-reconstruction`：默认明确不是 CAD、BIM、测绘或数字孪生。
- `evidence_policy`：列出会让下游报告失效的输入，并要求 HTTP 资产哈希与同轮封印。

默认精度为视觉级实时资产，不宣称 CAD、BIM、施工或数字孪生精度，除非用户提供相应原始资料和验收标准。

## 5. DirectionSet

生成顺序：

1. `white-idle`：暖白模型、固定三分之四机位、完整落地、无临时光效。
2. 每个已选光效的 `<effect>-mid`：从同一母版编辑，只改变目标材质显现和临时光效状态。
3. `final-real-material`：同一主体、构图和机位的真实材质完成态。

每张图记录 `role / path / prompt_id / source_ids / created_at / sha256`。整个集合固定：

- `provider=image_gen.imagegen`
- `no_third_party_fallback=true`
- `structure_truth=false`
- `conflict_policy=real-sources-win-structure`

方向图不得新增未被来源支持的塔冠、开口、楼层、支撑或附属体。如果生成图中出现，先编辑消除或在 ModelBrief 中明确排除。

## 6. 建模迭代

每个阶段都保存结构化 finding。只有用户明确要求阶段截图/逐轮确认时，才保存 raster capture 和 Reviewer 包：

| 阶段 | 重点 | 禁止跳过 |
| --- | --- | --- |
| `blockout` | 总体长宽高、原点、落地、主负空间 | front、side、roof、three-quarter |
| `macro` | 主体分区、层级、塔冠/屋顶/基座 | back、ground-contact |
| `meso` | 立面节奏、桁架族、开口和连接 | 左右差异、连续结构 |
| `micro` | 可见边缘、节点密度、收口 | 常用镜头和紧凑视口 |
| `white-approved` | 无材质识别度和几何完整性 | 七视角全部 |
| `material` | 证据化材质分区 | 未知项报告 |
| `lighting` | 光效特征、状态不变量和时间连续性 | 0/mid/1、真实暂停、replay、连续播放、模式切换、后台恢复、完成态 |

机器迭代至少写明 `expected / observed / finding / correction`，不只记录“通过”。若启用视觉复核，再补 `capture_path / capture_sha256 / reviewer / reviewed_at`。

## 7. DeliveryManifest 与 ComparisonReport

`DeliveryManifest` 至少包含：

- 模型路径、SHA-256、bytes、triangles、vertices、parts 和 materials。
- 生成源码入口、运行时入口和 acceptance bridge 名称。
- 已选光效、默认光效、状态不变量和 viewport profiles。
- acceptance bridge 版本、animation loop owner、visibility 生命周期和 shader 预热策略。
- Khronos 报告、内部/运行时报告和带 `motion_stability` 的浏览器报告；仅在视觉验收被明确授权时登记截图目录。
- evidence seal 路径/哈希、run ID、当前源码/运行时/报告哈希、HTTP 资产哈希与案例 dirty paths。
- 已知风险、排除项、临时产物和清理状态。

`ComparisonReport` 为每个标准视角分别保存：

- 真实来源 ID；视觉验收被授权时再登记对应截图。
- 方向图角色；视觉验收被授权时再登记对应截图。
- 明确授权视觉验收时保存最终运行时截图与 SHA；默认 `user-self-check` 只保留人工验收动作和失败信号。
- 结构事实结论、视觉方向结论、差异、修复和验收状态。
- 与最终模型一致的 `asset_sha256`。

## 8. 阻塞与停止条件

出现以下任一条件时停止并报告：

- 内置 `image_gen.imagegen` 不可用、失败或无法包含全部目标素材。
- 无法确认建筑目标版本、主体身份或关键尺寸。
- 用户素材与权威资料存在会改变模型主体的冲突。
- 目标工作树改动与任务文件直接重叠，继续会覆盖用户工作。
- Khronos Validator 报告 error、真实浏览器无法加载 GLB，或关键视角暴露结构错误。
- `seal_evidence.py` 发现报告陈旧、HTTP 字节哈希缺失、GLB/图片格式伪造或任一证据哈希漂移。
- 光效只能通过全局曝光、整圈泛光或镜头漂移伪造，无法满足所选模式合同。

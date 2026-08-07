# 阶段4：提示词封装（Prompt Pack）

**目标：** 把阶段3的 Copy Spec 原样封装成可复制的提示词包（Prompt Pack）。阶段4不负责改文案，只负责：模板拼装、风格一致、参数/约束齐全、避免模型乱加字。

## 封装原则（避免和阶段3混淆）

- **Copy Spec 是唯一真值**：提示词中"必须逐字放入"的文字，直接来自阶段3，不在这里重写。
- **提示词负责"怎么画"**：画幅、版式、留白、对齐、图标隐喻、风格块、强制约束、负面提示、参数。
- **封面类默认"禁额外小字"**：明确写"除指定文字外不要生成任何额外文字"。
- **Style × Layout 动态读取**：根据阶段2确认的 Style ID 和 Layout ID，动态读取对应的风格块和结构模板。

## 生成步骤（按顺序）

1. **读取 Style × Layout 组合**
   - 从阶段2获取 Style ID 和 Layout ID
   - 根据 Layout ID 查找对应的结构模板文件
   - 根据 Style ID 读取对应的风格块文件

2. **动态读取风格块**：
   - 根据阶段2确认的风格 ID，读取对应的风格块文件：
     - `cream-paper` → `templates/style-block-cream-paper.md`
     - `infographic` → `templates/style-block-infographic.md`
     - `handdrawn` → `templates/style-block-handdrawn.md`
     - `healing` → `templates/style-block-healing.md`
     - `sokamono` → `templates/style-block-sokamono.md`
     - `minimalist-sketch` → `templates/style-block-minimalist-sketch.md`
     - `xhs-cartoon` → `templates/style-block-xhs-cartoon.md`
     - `editorial` → `templates/style-block-editorial.md`
   - **风格基准锁定**：每张图都必须以读取的风格块定义作为**唯一允许的基础风格**来生成。
   - **不得换风格**：不要让模型自行切换成其他风格（如扁平矢量海报风/3D/摄影写实等）。
   - 允许你用自己的话描述该风格，但不能删掉关键要素与负面约束（否则风格会被模型先验带偏）。

3. **动态读取结构模板（Layout 维度）**：
   - 根据阶段2确认的 Layout ID，读取对应的结构模板：
     - `balanced` → `templates/16x9-infographic.md`
     - `comparison` → `templates/16x9-contrast-2cards.md`
     - `list` → `templates/16x9-3cards-insights.md`
     - `flow` → `templates/16x9-5panel-comic.md`
     - `sparse` → `templates/16x9-cover-roadmap.md`

4. 写清楚画幅/用途（PPT远看 vs 手机近看）与排版硬约束（对齐、留白、字号）
5. 粘贴 Copy Spec 的"必须逐字放入的文字"
6. 加强制约束 + 负面提示（无乱码/不加字/不密集小字/不背景杂乱）

## 模板使用

### 风格块（Style 维度，8种）

| Style ID | 风格块文件 | 画幅 |
|----------|-----------|------|
| `cream-paper` | `templates/style-block-cream-paper.md` | 16:9 |
| `infographic` | `templates/style-block-infographic.md` | 4:3 |
| `handdrawn` | `templates/style-block-handdrawn.md` | 4:3 |
| `minimalist-sketch` | `templates/style-block-minimalist-sketch.md` | 3:4 |
| `healing` | `templates/style-block-healing.md` | 3:4 |
| `sokamono` | `templates/style-block-sokamono.md` | 3:4 |
| `xhs-cartoon` | `templates/style-block-xhs-cartoon.md` | 3:4 |
| `editorial` | `templates/style-block-editorial.md` | 16:9 |

### 结构模板（Layout 维度，5种）

| Layout ID | 结构模板文件 | 信息密度 | 适用场景 |
|-----------|-------------|:--------:|---------|
| `balanced` | `templates/16x9-infographic.md` | 中等 | 解释原理、概念图解 |
| `comparison` | `templates/16x9-contrast-2cards.md` | 中等 | A vs B 对比 |
| `list` | `templates/16x9-3cards-insights.md` | 中高 | 要点清单、洞察 |
| `flow` | `templates/16x9-5panel-comic.md` | 中等 | 流程步骤、故事线 |
| `sparse` | `templates/16x9-cover-roadmap.md` | 低 | 封面、目录、概览 |

### 模板变量

结构模板中使用以下变量占位符，将被实际内容替换：

| 变量 | 说明 | 示例 |
|------|------|------|
| `{{STYLE_BLOCK}}` | 风格描述块（来自风格块文件） | 极简手绘笔记风格... |
| `{{LAYOUT_BLOCK}}` | 布局约束块（来自结构模板文件） | 三栏布局，每栏一个要点... |
| `{{TITLE}}` | 图片标题 | 估值对比 |
| `{{COPY_SPEC}}` | 阶段3确定的文案定稿 | SpaceX vs xAI... |
| `{{ASPECT_RATIO}}` | 画幅比例 | 16:9 |
| `{{RESOLUTION}}` | 分辨率 | 2560x1440 |

## 本阶段输出物

- **Prompt Pack**：按"图1/图2/…"编号输出；每张图使用标准格式（见下文）；便于 image-gen 解析

### 输出格式规范（与 image-gen 兼容）

每张图的输出必须遵循以下格式，确保 image-gen 能够正确解析：

```markdown
## 【封面图｜标题：xxx】
**核心内容**：一句话描述这张图的核心信息
**Style × Layout**：cream-paper × sparse
**绘画提示词**：
[完整的生图提示词，包含风格、构图、色彩等要求]

**负面约束**：[可选] 需要避免的元素
**参数**：比例 16:9，分辨率 2560x1440

## 【配图1｜标题：xxx】
**核心内容**：一句话描述这张图的核心信息
**Style × Layout**：cream-paper × balanced
**绘画提示词**：
[完整的生图提示词]

**负面约束**：[可选]
**参数**：比例 16:9，分辨率 2560x1440
```

**格式要求：**
1. 使用 `## 【封面图｜标题：xxx】` 或 `## 【配图N｜标题：xxx】` 作为标题
2. 必须包含 `**Style × Layout**：` 标记，显示 Style 和 Layout 组合
3. 必须包含 `**绘画提示词**：` 标记，提示词内容紧随其后
4. 可选包含 `**负面约束**：` 和 `**参数**：` 元信息
5. 封面图用 `【封面图` 标记以便 image-gen 识别
6. 不再使用代码块包裹提示词（改用标记格式）

## 为什么"阶段4"容易风格跑偏（解释逻辑）

阶段4本质是"用文字去约束一个带强默认审美的出图模型"，风格会被多方力量拉扯：

1. **模型先验（Style Prior）**：很多模型看到 "infographic/信息图" 会自动偏向"干净的扁平矢量/海报风"，即使你写了彩铅水彩，也可能只被当作弱建议。
2. **可读性约束会压过质感**：当你同时要求"中文大字号、严格对齐、少字、清晰"，模型会优先保证字清楚与版式稳定，牺牲纸纹、彩铅笔触等"质感细节"。
3. **风格基准不够"排他"会降权**：如果不强调"这是唯一允许风格，不能换"，模型会把它当成"可选项"，然后自动回到信息图的默认风格（常见是扁平矢量/海报风）。
4. **风格词太短/太抽象**：仅写"彩铅水彩"不足以锁定细节，需要补"纸纹可见、笔触可见、轻晕染"等可观察特征，并配合负面约束（已在风格块中补强）。

实操上要提升稳定性：在每张图的 prompt 里都明确"以该风格为唯一基础，不得换风格"，并加入"不要扁平矢量/不要3D/不要摄影"等负面约束来对冲模型的默认风格。

## Style × Layout 兼容性速查表

| Style ↓ / Layout → | balanced | comparison | list | flow | sparse |
|-------------------|:--------:|:----------:|:----:|:----:|:------:|
| `cream-paper` | ✅✅ | ✅ | ✅✅ | ✅ | ✅✅ |
| `infographic` | ✅✅ | ✅ | ✅ | ✅ | ✅ |
| `handdrawn` | ✅✅ | ✅ | ✅✅ | ✅✅ | ✅ |
| `minimalist-sketch` | ✅✅ | ✅ | ✅ | ✅ | ✅ |
| `healing` | ✅ | ⚠️ | ✅ | ✅✅ | ✅ |
| `sokamono` | ✅ | ✅ | ✅ | ✅✅ | ✅ |
| `xhs-cartoon` | ✅✅ | ✅ | ✅✅ | ✅ | ✅ |
| `editorial` | ✅✅ | ✅✅ | ✅ | ✅ | ✅ |

✅✅ = 高度推荐 | ✅ = 兼容 | ⚠️ = 需谨慎 | ❌ = 不推荐

## 风格与画幅对照表（供参考）

| 风格 ID | 画幅 | 特点 |
|---------|------|------|
| `cream-paper` | 16:9 横版 | 默认风格，通用 |
| `infographic` | 4:3 横版 | 扁平科普，适合解释原理 |
| `handdrawn` | 4:3 横版 | 方格纸手绘，学习笔记感 |
| `minimalist-sketch` | 3:4 竖版 | 极简手绘，专业技术 |
| `healing` | 3:4 竖版 | 治愈插画，情绪叙事 |
| `sokamono` | 3:4 竖版 | 描边插画，清新文艺 |
| `xhs-cartoon` | 3:4 竖版 | 小红书卡通，莫兰迪色 |
| `editorial` | 16:9 横版 | 社论全景，对比分析 |

# 纸墨线稿 · 图形化表达与组件规约

> **排版决策由 `layout-primitives.md` 的原语驱动，不由版式/组件驱动。** 版式画册（layouts.md / gallery）和 atlas 组件库都是**参考样本**——AI 从原语推导出布局后，翻阅它们借鉴坐标和图元画法，但不是"必须从中选一个"。
> **图形化优先**：把关系画出来、把数字画出来；禁止"同构框+字+箭头"阵列充当图形。
> 本文件规定三件事：自由 SVG 的手法规约、外部库（FontAwesome/ECharts）的纸墨化、atlas 组件的改造五步（作为复杂形状的素材来源，非兜底降级）。

---

## 一、自由 SVG 手法（首选）

- **星座式点线网络**：小方块/圆点节点 + 细线连接，密度与连线即语义（比"框+箭头"高级）；权重用线宽/透明度三档编码。
- **构造线不擦除**：辅助圆、虚线基准、作图痕迹保留，铜版画测绘感。
- **精密细线可画具象物**：仪器/建筑/生物/场景，不限于抽象图表；hatch 排线表达明暗。
- **字符即图形**：mono 字符流密度构成明暗（`particles.js textPoints`）。
- 线宽/节点/箭头/刻度规约全部查 `design-tokens.md` 第三章。

## 二、FontAwesome 图标（按需）

- CDN：`https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css`（`shot-template.html` 里有注释掉的链接，用时解开）。
- 强制墨色（`color: var(--ink)` 或透明度阶梯）；禁彩色、禁动效。
- 尺寸 ≤32px，配 mono 小标签做标注件；不当主角。

## 三、ECharts 复杂数据图（按需，纸墨化强制）

- CDN：`https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js`（模板注释链接）。权威参考：官网 `https://echarts.apache.org`。
- 仅用于折线/柱状/散点等真实复杂数据图；能用细线 SVG 画的不用库。
- **去色改造清单**：
  - `color: ['#191917','rgba(25,25,23,.55)','rgba(25,25,23,.3)','rgba(25,25,23,.15)']`；
  - `axisLine / axisTick / splitLine`：0.6–1px，墨 25–50%；axisLabel 用 Courier Prime 12–13px；
  - 去 `shadow` / 渐变 / 圆角；areaStyle 只允许 `rgba(25,25,23,.06)` 一档；
  - 图例/提示框：细线框 + 纸底，无阴影；字体走 `shared.css` 变量；
  - 数据全部自编（名称与数值虚构）。

## 四、atlas 组件改造（兜底）

> html-ppt-components（本地 skill：`ppt-component-atlas`，catalog 61 个组件）是我们自己的组件库，版权自有，可自由改造。
> **atlas 组件提供结构骨架，纸墨线稿提供皮与尺。** 仅当 layouts 没覆盖且自绘成本过高时使用。

---

### 4.1 导出组件

```bash
# 列出全部组件
node ~/.codex/skills/ppt-component-atlas/scripts/export-component-html.mjs --list

# 按中文/英文名导出（PPT 场景统一用 --static 静态版，不带入场动效）
node ~/.codex/skills/ppt-component-atlas/scripts/export-component-html.mjs \
  --query "金字塔" --static --out-dir <deck目录>/components
```

- 导出产物是裸 HTML（最小 html/head/style/body + 组件 CSS + 组件 DOM）。
- 多候选时脚本返回 `status: "ambiguous"`，先把候选列表给用户选，不要自动取第一个。
- 线上预览：`https://wisewong.com/#tab=html-ppt-components`（选组件用，不是交付物）。

### 4.2 改造五步法（每个导出组件都要过一遍）

### 第 1 步 · 去色
- 组件内所有彩色值（hex/rgb/hsl/命名色）全部替换为墨色阶梯：`#191917` 或 `rgba(25,25,23,.8/.7/.45/.25/.12)`。
- 原组件的"主色强调"翻译成线宽/字重/填充差异：主色块 → hatch 剖面填充或 1.8px 强调线；浅色底 → 柔白 `rgba(255,255,255,.22)`。
- 彩色图标/彩色徽章 → 双线框 + mono 文字。

### 第 2 步 · 换字
- 标题 → 思源黑体 400（卡题 24–26px）；需要大字级别才上思源宋体 Medium。
- 正文/说明 → 思源黑体 300（18–22px）。
- 数字/编号/标签/英文 → Courier Prime（13–20px，uppercase + 字距 .22–.3em）。
- 删除组件自带的字体声明与 CDN 引入，统一走 `shared.css` 的 `@font-face`。

### 第 3 步 · 降线
- 边框统一降到 **1px** @ 墨 38–80%（UI 组件边框一律 1px，深浅靠颜色阶梯）；SVG 图形主轮廓 1.2–1.4px、装饰线 0.6–0.7px。
- 粗描边（≥2px）只保留给"全页唯一强调"（每页至多一处）。
- 圆角：卡片/气泡保留 16–18px；图版元素（图表格、矩阵格）改直角。
- 删 atlas 自带的 `box-shadow`/渐变/`filter`；如需质感阴影，替换为 `var(--shadow-soft)`（卡片/面板）或 `var(--shadow-specimen)`（标本卡），同层级不叠影。

### 第 4 步 · 入台
- 组件 DOM 整体放进 `.stage`（1920×1080），外层包缩放定位容器或重写为 SVG 坐标。
- 链接 `shared.css` + `particles.js`，补三件套：`.doc.tl` 角注、`.folio` 页脚、`.caption` 结论句。
- 工程制图类组件补 `FIG. NN` 图题 + 短横线。

### 第 5 步 · 对齐规约
- 过一遍 `design-tokens.md`：安全区（左右 150–220、纵向 y170–880）、字号阶梯、线宽表。
- 过一遍 `checklist.md`。

## 五、高频需求 → 组件/版式映射

| 要表达什么 | 优先用 | 备选 |
|---|---|---|
| 递减/筛选/转化 | layouts B11 漏斗（连续收尖版） | atlas「金字塔 / 倒金字塔」改造（塔尖必须收为点） |
| 概念构成/分类 | layouts B7 四象限 | atlas「矩阵」改造（双线框 + 中心圆标） |
| 层级/树 | layouts B8 环节树 | atlas「组织架构 / 树形图」改造（竖干 0.8px + 落点圆点） |
| 对比 | layouts B4 双面板 / B5 分水岭 | atlas「前后对比」改造（页签 + VS 徽章） |
| 流程/步骤 | layouts B1 流水线 | atlas「流程 wrapped」改造（等长箭头 + 圆环序号） |
| 闭环 | layouts B12 循环圆环 | atlas「循环」改造（15° 刻度 + 弧箭头） |
| 时间/里程碑 | layouts B6 时间轴 | atlas「时间线」改造（38px 刻度齿 + 双圈节点） |
| 多对多映射/组合 | layouts B15 星座映射网 | B2 弧线图（权重三档编码） |
| 大数字指标 | 自绘 big-stat：超大 mono 数字（>80px）+ 右侧标签/变化 + 迷你 SVG 刻度 | atlas「数据」改造 |
| 引用/金句 | 自绘 quote-block：文楷大字 + 短横 + mono 署名（衬线气质） | layouts C2 金句页 |
| 风险/边界 | 自绘 alert-box：高对比细边框（1px 墨 80%）+ mono 标签，少量克制 | B5 栏内警示行 |
| 代码/配置片段 | 自绘 terminal-box：Courier Prime + 柔白低对比底 + 细线框 | — |
| 数据/排行 | 重做：mono 数字 + hatch 条（参照 B1 条形区） | atlas 图表类改造（去彩色、去圆角、坐标轴细线化） |
| 复杂数据图（折线/柱状/散点） | ECharts 去色改造（本文件第三节） | 自绘细线 SVG |
| 图标标注 | FontAwesome（墨色，≤32px，本文件第二节） | 自绘细线小图标 |
| 列表/要点 | B8 规格单（mono 字段码 + 中文双列） | atlas「列表 / 卡片组」改造 |

**原则**：layouts.md 里有同构版式的，优先抄样本页的结构（它已通过 20 页验证）；atlas 组件只兜底 layouts 没覆盖且自绘成本过高的形状。

## 六、不要做的事

- 不要把 atlas 组件的配色/字体/阴影带进成品页（改造五步是强制的，不是可选的）。
- 不要把 atlas 的动效层带进 PPT 页（统一 `--static`；视频分镜需要动效时另行手写）。
- 不要改 atlas 的 `public/catalog-data.js` 源数据（改造只作用于导出文件）。
- 不要让用户自己去图册页翻组件——由你查 `--list` 或线上图册，给准确导出文件。

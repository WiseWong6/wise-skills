# 纸墨主题视觉自检

先跑机器门禁：

```bash
python3 scripts/validate.py gallery .
python3 themes/paper-ink/scripts/lint.py gallery/paper-ink/general
python3 themes/paper-ink/scripts/lint.py gallery/paper-ink/ai
bash runtime/check-deck.sh <deck-dir> --mode normal
bash runtime/check-deck.sh <deck-dir> --mode accent
```

机器检查通过后，由用户在实际浏览器逐页目检。只有用户明确要求视觉代验或截图交付时才生成截图；构建成功不能替代人工视觉验收。

## P0：必须通过

- 页面为 1920×1080，`.stage` 等比适配且无横纵溢出。
- `data-page-id`、`data-page-role`、`data-theme`、`data-layout-source`、`data-emphasis-mode` 齐全；Gallery / Composition 页另有 `data-recipe-id`，存在页面级字体覆写时才有 `data-typography-mode`。这些值必须与 Deck Plan、主题和 Render Plan 的派生值一致。
- Gallery 的每个 recipe 槽位有 `data-slot-id`；Composition / Custom 的每个表达块有 `data-block-id`。所有内容载体都有 `data-renderer-kind`、`data-component-source`、`data-component-id`、`data-theme-adapter-id` 和 `data-content-ref`。
- 纸底、墨色、字体、线宽符合 `design-tokens.md`；无未声明的彩色、渐变、重阴影和大面积深色底。
- 页面没有用 Emoji 代替图标或装饰；通用图标来自本地 `WisePPT.icons` registry 或符合主题线宽的自绘 SVG，不存在 Font Awesome / 图标字体依赖。
- 全 deck 字号只引用共享 `--type-*` 字阶；相同语义层级字号一致，CSS/SVG/Canvas/ECharts 都没有页面级裸字号或 shorthand 绕过。
- 一页只有一个主要视觉角色；支持组件没有抢走结论。
- 事实、数字、表格、图表和重构图都能追到 `content.json`；推断或占位没有伪装成来源事实，原始图片没有进入最终页面。
- 每个 renderer 与结构区域的 item 数在各自机器合同内；超限时换 recipe、换 renderer 或拆页，不用一个页面级数字替代实际承载判断。
- 居中只用于中心型原语；非对称、时间轴、UI、证据墙、架构和流程按自身结构线对齐。
- ECharts、图片和每个必需字体 face 真实加载完成后才调用 `WisePPT.markSlideReady(slide)`；全部页面完成后根节点必须同时是 `data-font-check="pass"` 与 `data-deck-ready="true"`。
- caption 没有被主体压住且全 deck 固定为 `--type-caption`；正文只用 `--type-body` / `--type-body-small`；图表刻度与来源可读。
- 放映正文逐页可框选复制；input 与 contenteditable 分别获得焦点时，方向键、空格、Home/End 和触控滑动不抢占；真实 ESC KeyboardEvent 返回画册。
- 1920×1080 `#deck-stage` 的 bounding rect 始终完整落在 visual viewport；正式 `.slide` / `.stage` 没有 inline transform，也没有第二次缩放。
- 右下控制区使用本地线性 SVG、纸墨浅色 token，触控区 ≥40px，未进入系统安全区，打印时隐藏。

## P1：主题一致

- 全 deck 只选择一种登记字体模式：默认混合、全黑体或全宋体。默认混合模式下重点用思源宋体、正文与 UI 用思源黑体；表格数字、时间、编号与坐标固定 Courier Prime，真实手写批注固定霞鹜文楷。
- 卡片和 UI 边框 1px；SVG 主轮廓 1.2–1.4px；粗强调线每页最多一处。
- 构造线、引线、节点、hatch 都在表达语义，不是填空装饰。
- `?accent` 开启时一页一色、面积 ≤2.5%，且只染 Render Plan 指定主角的语义焦点组；`data-emphasis-ref`、`data-emphasis-roles` 和载体 `data-emphasis-role` 必须精确对应，关闭后回到纯单色。
- 检查是否为了上色新增了原稿不存在的圆圈、图标、标签或装饰；没有语义对应物时应保持单色，不得硬造载体。
- ID、hash、运行状态圆点、栏题、图例、刻度、FIG 与页脚默认保持墨色；空间邻近不能成为跟随上色的理由。
- 主角图表使用 hatch 时，内部斜线须和数值/边框共同响应；同时确认复用 pattern 的其他图形没有被误染。
- Grid 仅用于同级并列或二维关系；证据墙、六宫格和矩阵都能说明“为什么是这些格”。
- 复用相同 layout 时仍须逐页满足语义、容量、slot 与主次条件；不得只因连续出现就强行换成不匹配的版式。

## P2：整套节奏

- 页数与叙事弧来自 deck plan，不强制固定骨架；封面和收尾服务真实场景，不为凑格式存在。
- 复合信息页前后有必要的节奏变化，但不机械规定每若干页必须插入固定页型。
- 大字、金句、粒子、手写批注都克制使用；重复是为了形成节奏，而非暴露模板痕迹。
- general 与 ai 两册同一 recipe 的结构一致，内容主题不同；画册总数与公共 Gallery manifest 完全一致。

## 浏览器目检顺序

1. 远观：主张、主角和阅读方向是否一眼可见。
2. 中距：证据、层级、组件组合和留白是否服务主张。
3. 近看：同层级字阶是否跨页一致，线宽、对齐、来源、单位、标注和溢出是否合格。
4. 对照：与公共 Gallery manifest 中同一 `recipe_id` 的 general/ai 样例并排，按语义对应物确认强调规则一致；允许两册缺少不同载体，不得为了结构齐整凭空补件。

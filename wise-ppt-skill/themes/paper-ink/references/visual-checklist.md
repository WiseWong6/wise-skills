# 纸墨主题视觉自检

先跑机器门禁：

```bash
python3 scripts/validate.py gallery themes/paper-ink
```

机器检查通过后，再对实际浏览器截图逐页目检。构建成功不能替代视觉验收。

## P0：必须通过

- 页面为 1920×1080，`.stage` 等比适配且无横纵溢出。
- `data-page-id`、`data-page-role`、`data-theme`、`data-layout`、`data-density`、`data-reuse-mode` 齐全并与 render plan 一致。
- 所有组件有 `data-block-id`、`data-provider`、`data-component`、`data-content-ref`。
- 纸底、墨色、字体、线宽符合 `design-tokens.md`；无未声明的彩色、渐变、重阴影和大面积深色底。
- 一页只有一个主要视觉角色；支持组件没有抢走结论。
- 事实、数字、表格、图表和截图都能追到 `content.json`；推断或占位没有伪装成来源事实。
- density 与承载量一致：breathing 留白 ≥60%；balanced 为 3–5 个语义单元；dense 通过安全区、字号、遮挡、层级与溢出检查。
- 居中只用于中心型原语；非对称、时间轴、UI、证据墙、架构和流程按自身结构线对齐。
- ECharts、图片和字体加载完成后才由 `markRenderReady()` 设置页面根节点的 `data-render-ready="true"`；截图工具只接受这个唯一 ready 标记。
- caption 没有被主体压住；最小正文 16px；图表刻度与来源可读。

## P1：主题一致

- 标题/金句/大字使用衬线气质族；正文/数据/UI/标签使用无衬线或 mono。
- 卡片和 UI 边框 1px；SVG 主轮廓 1.2–1.4px；粗强调线每页最多一处。
- 构造线、引线、节点、hatch 都在表达语义，不是填空装饰。
- `?accent` 开启时一页一色、面积 ≤2.5%，且只染 render plan 指定的主角；关闭后回到纯单色。
- Grid 仅用于同级并列或二维关系；证据墙、六宫格和矩阵都能说明“为什么是这些格”。
- 同一 deck 不连续三页复用相同 layout；复用时仍须根据内容数量和主次做适配。

## P2：整套节奏

- 页数与叙事弧来自 deck plan，不强制固定骨架；封面和收尾服务真实场景，不为凑格式存在。
- 高密度页前后有必要的节奏变化，但不机械规定每若干页必须插呼吸页。
- 大字、金句、粒子、手写批注都克制使用；重复是为了形成节奏，而非暴露模板痕迹。
- general 与 ai 两册同一 layout 的结构一致，内容主题不同；画册总数与 manifest 完全一致。

## 截图目检顺序

1. 远观：主张、主角和阅读方向是否一眼可见。
2. 中距：证据、层级、组件组合和留白是否服务主张。
3. 近看：字阶、线宽、对齐、来源、单位、标注和溢出是否合格。
4. 对照：与 manifest 中同一 `layout_id` 的 general/ai 样例并排，确认结构同源但内容没有被模板改写。

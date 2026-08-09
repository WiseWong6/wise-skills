# 组件路由

本文件是组件路由的唯一规则源。布局规则见 `layout-gallery.md`，媒体重构规则见 `media-contract.md`。

## 两条独立轴

每个组件同时声明 `renderer_kind` 和 `component_source`，不得用其中一个字段代替另一个字段。

- `renderer_kind` 回答组件最终如何出现在页面上。允许值只有 `typography`、`table`、`image`、`native-html`、`svg`、`canvas`。
- `component_source` 回答组件来自哪里。允许值只有 `native`、`echarts`、`ppt-component-atlas`、`codex-host`。

合法组合以 `capabilities/registry.json` 为准。Gallery 只提供布局配方，不是组件来源。

## 选择顺序

1. 先判断信息需要精确查值、定量图表、独特关系图、媒体画面还是普通排版。
2. 再选择能完成该任务的 `renderer_kind`。
3. 最后选择 `component_source` 和稳定的 `component_id`。
4. 主题只通过 `theme_adapter_id` 做视觉适配，不改变组件的语义和数据。

优先使用最简单且足以表达信息的组合。原生排版已经能清楚表达时，不为展示技术而引入 ECharts 或 Atlas。

## 来源规则

### Native

使用 `native` 承载自有的文字、表格、图片、HTML、SVG 或 Canvas 组件。`component_id` 必须稳定，不能写临时名称。

### ECharts

使用 `echarts` 承载需要趋势、分布、构成、相关或地图编码的定量图表。`renderer_kind` 只能是 `svg` 或 `canvas`。业务数据与 ECharts option 分离：Render Plan 用 `data_ref`、`dataset_id`、`encode` 声明绑定；HTML 用同名 `data-dataset-id` 和同页 JSON 数据块承载真实数据；运行时在绘制前核对 option.dataset 与该数据块完全一致。

### PPT Component Atlas

仅在已经确定精确组件名时使用 `ppt-component-atlas`。先查询目录，再记录精确 `component_id`，最后导出裸 HTML。不得把模糊检索结果当成已选组件。

### Codex Host

使用 `codex-host` 承载 Codex 宿主内置图片能力生成或重构的媒体。`renderer_kind` 固定为 `image`。不得回退到第三方生图 Skill、CLI 或 API。

## 失败处理

目标来源不可用时，重新选择合法组合或暂停说明阻塞原因。不得把来源名称塞进 `renderer_kind`，也不得伪造未注册来源。

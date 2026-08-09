# Render Plan 的布局来源决策

本文件只规定 Core 如何把公共能力的评估结果写入 Render Plan。Gallery recipe 的结构与匹配算法以 [`../../capabilities/references/layout-gallery.md`](../../capabilities/references/layout-gallery.md) 为唯一规则源；renderer 与组件来源以 [`../../capabilities/references/component-routing.md`](../../capabilities/references/component-routing.md) 为唯一规则源；媒体处理以 [`../../capabilities/references/media-contract.md`](../../capabilities/references/media-contract.md) 为唯一规则源。

## 固定决策链

严格按以下顺序：

`页面语义 → 查询公共 Gallery → 记录实际评估的全部候选 → 决定布局来源 → 选择公共组件 → 应用主题 adapter → 验证`

查询前，Deck Plan 必须已经确定 takeaway、页面角色、主要关系、空间原语、内容引用和唯一 primary block。Render Plan 不得为了迁就某个 recipe 反向改写这些语义。

## 三种布局来源

### `source: gallery`

公共 Gallery 评估器返回唯一完整命中时，必须直接选择该 `recipe_id` 并停止继续组合。Render Plan 只按 recipe 的完整 reading order 写 `payload.bindings[]`，不得声明页面 `slots[]`，也不得替换默认组件。

### `source: composition`

没有完整命中，但某个 recipe 的结构适合且需要替换组件时，选择该 `recipe_id` 作为结构合同。页面必须完整保留其 slot 集合、顺序、区域关系和主次，再为每个 slot 选择公共 renderer。

### `source: custom`

实际评估的 Gallery 候选均不适合时，声明 `custom_contract.reading_order` 与 `regions[]`。Custom 不写 recipe ID，每个 region 必须与页面 block 一一对应。

## 机器复核

Validator 不接受 AI 自报的匹配结论。它必须用 Deck Plan 的角色、主要关系和空间原语复核候选，并用公共 manifest 复核完整 slot 集合、reading order、默认 renderer 与组件容量。

发现完整命中却选择 Composition 或 Custom、Gallery 漏绑任一 slot、Composition 改变结构，或 Custom 冒充 recipe 时，均直接失败。

## 进入 HTML 前的停止条件

- 用户仍有未决定问题；
- 页面语义与所选 recipe 不一致；
- renderer 或 component source 未在公共 registry 登记；
- 主题 adapter 不支持该公共能力组合；
- 数据绑定、媒体重构链或内容引用无法闭合。

任何停止条件存在时，不得继续构建 HTML 或导出 PDF。

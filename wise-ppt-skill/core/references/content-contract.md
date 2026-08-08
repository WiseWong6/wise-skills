# 内容契约：从原始素材到 `content.json`

`content.json` 是整份 deck 的事实层。它回答“用户到底给了什么、哪些必须保留、哪些仍不确定”，不负责页数、版式或视觉风格。

权威结构见 `../schemas/content.schema.json`。

## 1. 先登记来源，再整理内容

每份可追溯输入都要进入 `sources[]`，包括用户口述、粘贴文本、文件、网页、数据集和图片。`locator` 写可复查的位置；无法提供公开链接时，也要写清文件路径、页码或“本轮用户原话”。真实输入写 `synthetic: false`；专供演示或测试的合成输入必须写 `synthetic: true`。

整理内容时遵守三条规则：

1. 不润色事实本身。原始数字、单位、日期、专名和限定词原样保留。
2. 不把推断伪装成事实。AI 补出的桥接判断使用 `status: inferred`，并在 `status_note` 说明依据。
3. 不用假数据填空。确实需要等待用户补充时使用 `status: placeholder`；展示型假数据也必须保留该标记，不得写成 `sourced`。

## 2. 三种状态

| `status` | 含义 | 必须满足 |
|---|---|---|
| `sourced` | 输入中可以直接核对 | `source_refs` 至少一个，`status_note` 可为空 |
| `inferred` | 根据已知材料推导 | `status_note` 写推导依据；涉及 must 内容时触发确认 |
| `placeholder` | 尚未获得真实值 | `status_note` 写待补内容；涉及 must 内容时触发确认 |

来源互相冲突时，保留两个版本及其各自来源，不自行择一；在对应内容项的 `relations[]` 中使用 `contradicts` 指向冲突项，同时把冲突写入 `brief.gaps`，交给语义规划层触发确认。

## 3. 内容关系是事实层的一部分

每个内容项都必须带 `relations[]`，没有已知关系时写空数组，保持机器结构稳定。关系项包括 `type`、`target_ref` 和非空 `reason`：

- `supports`：当前内容为目标主张提供证据；
- `contradicts`：两项不能同时被当成一致事实，必须触发确认；
- `depends_on`：理解或成立依赖目标项；
- `elaborates`：当前内容展开目标项，但不新增独立论证。

关系只能指向已存在的 `item.*` 或 `atom.*`。不要为了让叙事更顺而编造关系；无法确定时保持空数组，并在 gaps 中记录。

## 4. 优先级不是视觉层级

- `must`：交付中必须出现，除非用户明确同意删除或延后。
- `should`：在页数和叙事允许时保留。
- `could`：可作为补充、附录或删减候选。

优先级只决定覆盖策略，不直接决定字号、面积或颜色。视觉主次在 `deck-plan.json` 的页面与 block 中另行判断。

## 5. 原子值与覆盖检查

一个内容项可以包含多个不可丢失的 `atomic_values[]`。例如“一次上线包含六个阶段”，阶段名称应拆成六个稳定 ID，而不是藏在一段 prose 里：

```json
{
  "id": "item.launch-path",
  "kind": "process",
  "statement": "上线过程由六个连续阶段构成",
  "priority": "must",
  "status": "sourced",
  "status_note": "",
  "source_refs": ["src.brief"],
  "atomic_values": [
    {"id": "atom.stage.discover", "label": "阶段一", "value": "发现"},
    {"id": "atom.stage.scope", "label": "阶段二", "value": "界定"}
  ]
}
```

后续页面可以引用整个 `item.launch-path`，也可以直接引用 `atom.stage.discover`。覆盖校验会逐一检查 must 项及其原子值，避免“主题看似出现，细节实际丢失”。

## 6. Brief 缺失时的写法

目标、受众、场景缺失时写 `null`，并把缺口写入 `brief.gaps`；禁止猜一个看似合理的答案。`content.json` 仍然要生成，因为内部规划始终存在，是否暂停由 `deck-plan.json.confirmation` 决定。

页数只在这里记录用户给出的上下限或明确要求。实际页数及其理由属于语义规划层。

## 7. 完成条件

进入 deck 规划前，至少确认：

- 所有 ID 唯一，来源引用有效；
- 每个 relation 的目标存在，`contradicts` 已进入确认触发检查；
- 每条 sourced 内容可追溯；
- inferred / placeholder 有明确说明；
- must 内容已拆到不会被摘要吞掉的原子粒度；
- 真实数据没有被改写，合成数据没有被伪装成真实数据；
- `content.json` 通过 schema 与语义校验。

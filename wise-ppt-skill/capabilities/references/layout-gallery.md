# Layout Gallery

本文件是 Gallery 选版与复用的唯一规则源。Gallery 是公共布局能力，不属于任何 Theme。

## 权威文件

公共注册表位于 `capabilities/registry.json`，布局目录位于 `capabilities/layouts/gallery-manifest.json`。manifest 根级 `contract_version` 固定为 `2`，所有布局记录放在 `recipes[]`。

每个 recipe 使用稳定的 `recipe_id`，并声明以下结构信息：

- `roles`、`relations` 与 `primitives`
- `reading_order`
- `structure_contract` 与 `structure_fingerprint`
- `slots[]`
- `examples`

每个 slot 只在 `min_items` 和 `max_items` 中表达容量。不得恢复页面密度、语义计数或 provider 字段。

## 查询

先形成页面角色、信息关系和空间原语，再查询公共 manifest：

```bash
python3 scripts/catalog.py layouts \
  --role prove \
  --relation evidence \
  --primitive evidence-annotation \
  --renderer-kind svg \
  --component-source native
```

查询结果返回全部命中项，不截断为前三项，也不替调用方做主观排序。调用方必须记录所有实际评估过的候选及具体接受或拒绝理由。

## 完整命中

只有角色、关系、原语、区域数量、slot 集合、阅读顺序、结构指纹、每个 slot 的内容数量和默认组件都满足时，才算完整命中。

完整命中是终止路径：

1. 使用 recipe 声明的结构和所有 `default_renderer`。
2. 只绑定本页内容或数据。
3. 不替换组件，不增删 slot，不改变阅读顺序，不修改结构。

Gallery 没有 adapt 模式。任何组件替换或结构变化都必须离开 Gallery 路径，进入 composition 或 custom，并重新声明所用组件。

## 样张

`examples.general` 与 `examples.ai` 指向 `gallery/paper-ink/general/frames` 和 `gallery/paper-ink/ai/frames` 下的已验证实现。展示码只用于人工浏览；机器契约只使用 `recipe_id`。

不要一次性读取全部样张。先用 catalog 缩小候选，再打开真正需要评估的 HTML。

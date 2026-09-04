# Skill Optimizer · Skill 审计与优化

把 Skill 当成可发行产品进行审计和优化，以“权威源码 → 发行载荷 → Agent 安装入口/软链 → Agent 实际加载 → 真实任务”的生命周期证据图，检查传播拓扑、版本坐标、死重候选、测试体系、结构职责、依赖与交付闭环。

在 Agent 中调用 `$skill-optimizer`；审计模式、修改确认门禁和验证流程见 [SKILL.md](SKILL.md)。

依赖允许存在，但需要解释用途、阶段、体积与引入路径。优化顺序固定为“系统原生能力 → 已有依赖 → 新增依赖”；审计只输出有用途条件的替代候选，不自动删除依赖。

发行审核示例：

```bash
python3 scripts/audit_skill.py <发行 Skill 目录> \
  --surface release \
  --profile auto \
  --schema-profile codex \
  --supported-node-majors 22,24 \
  --source <权威源码 Skill 目录> \
  --release-manifest <发行 manifest> \
  --agent-entry codex=<Codex 安装入口> \
  --agent-entry agents=<Agents 安装入口> \
  --metafile <可选 esbuild metafile> \
  --format json
```

源码测试体系审核示例：

```bash
python3 scripts/audit_skill.py <源码 Skill 目录> \
  --surface source \
  --test-system-contract tests/<skill-name>/test-system.json \
  --format json
```

`release` 会自动启用 `review`。新增输出包括 `lifecycle`、`version_coordinates`、`runtime_verification`、`reachability`、`test_system` 和不含糊打分的 `structure` 矩阵。静态工具只产生 `deadweight-candidate`，不会确认删除；仅被 manifest 收录或来源标签提及不能证明运行使用。

测试语义由目标 Skill 的权威源码仓声明。源仓可用 `test-system.json` 登记唯一规则主人、case 所有权、共享/独立 runner 和受治理例外；审计器只校验声明与文件闭环，不执行目标测试，也不靠文件名或重复片段自动决定哪些脚本应该合并。缺少合同只进入人工复核，已采用合同后的漏登记或断链才阻断。

审计器只使用 Python 标准库，不运行目标代码、不自动联网、不安装第三方依赖，也不自动修复软链。`--supported-node-majors` 应由调用方按当前官方支持矩阵传入。

体积提醒不是删除结论。大型 Catalog、字体、示例和必要依赖可以保留；生成代码只有具备多项强证据时才标记“疑似混淆”，不能把“难读”直接写成“混淆”。

详细判据见 [生命周期审计判据](references/lifecycle-audit.md) 和 [测试体系审计合同](references/test-system-audit.md)；Codex/RedSkill 差异见 [平台 Schema Profile](references/platform-schemas.md)。

License: [MIT](LICENSE) © 2026 Wise Wong

# Skill Optimizer · Skill 审计与优化

把 Skill 当成可发行产品进行审计和优化，区分权威源码、用户发行包、安装副本与运行环境，检查合同、版本门槛、bundle 可追溯性、依赖与联网成本、跨平台适配和交付闭环。

在 Agent 中调用 `$skill-optimizer`；审计模式、修改确认门禁和验证流程见 [SKILL.md](SKILL.md)。

依赖允许存在，但需要解释用途、阶段、体积与引入路径。优化顺序固定为“系统原生能力 → 已有依赖 → 新增依赖”；审计只输出有用途条件的替代候选，不自动删除依赖。

发行审核示例：

```bash
python3 scripts/audit_skill.py <发行 Skill 目录> \
  --surface release \
  --profile auto \
  --supported-node-majors 22,24 \
  --source <权威源码 Skill 目录> \
  --metafile <可选 esbuild metafile> \
  --format json
```

`release` 会自动启用 `review`：大文件采用流式统计，检查版本声明冲突、生成 bundle 来源、发行分类占比、直接/传递与内联/外置依赖，以及 doctor/build/install 中的静态联网线索。审计器不运行目标代码、不自动联网、不安装第三方依赖。`--supported-node-majors` 应由调用方按当前官方支持矩阵传入。

体积提醒不是删除结论。大型 Catalog、字体、示例和必要依赖可以保留；生成代码只有具备多项强证据时才标记“疑似混淆”，不能把“难读”直接写成“混淆”。

License: [MIT](LICENSE) © 2026 Wise Wong

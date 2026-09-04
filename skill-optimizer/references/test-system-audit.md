# 测试体系审计合同

## 目的与职责

测试文件数量不能直接证明架构好坏。通用审计器也无法仅凭文件名、重复片段或选择器理解目标 Skill 的业务语义，因此职责固定为：

- 目标 Skill 的权威源码仓声明测试机制、规则主人、执行边界、case 所有权和真实例外。
- `skill-optimizer` 只读验证声明与当前文件是否一致，不执行目标测试、不聚类业务语义、不建议自动合并或删除。
- 没有合同只能输出测试/check/audit 文件的客观盘点和 `review`，不能声称“重复脚本”或“体系化问题已确认”。
- 源仓一旦采用合同，缺失引用、漏登记、重复共享边界和路径逃逸就是确定性合同违约。

目标不是把全部测试塞进一个大脚本，而是让案例可以增长，同时让执行器、规则主人和生命周期边界不会随案例线性增长。

## 五类边界

1. **全局不变量**：同一规则覆盖全部适用对象，由一个规则主人和共享 runner 验证。
2. **参数化 case**：同一失败机制的输入和预期作为数据增长，执行器保持不变。
3. **真实例外**：无法归入共享机制时，记录负责人、原因和退出条件，不把临时例外永久化。
4. **独立生命周期**：语言运行时、平台、外部工具或发布阶段确实不同，可以保留独立 runner，但必须显式说明边界。
5. **代表性 E2E**：只保留少量端到端路径验证集成结果，不复制所有底层 case。

页面、客户、平台或历史缺陷可以是合法 case；问题不在“有个案”，而在个案同时复制了规则、环境启动和断言执行器。

## 合同发现

CLI 可显式传入：

```bash
python3 scripts/audit_skill.py <Skill 目录> \
  --surface source \
  --test-system-contract <test-system.json> \
  --format json
```

相对合同路径按 Git 根解析；非 Git 目标按目标 Skill 根解析。未显式传入时按顺序发现：

1. `<git-root>/tests/<skill-name>/test-system.json`
2. 若仓库测试目录使用 Python 包命名，再检查把 Skill 名中 `-` 转为 `_` 的同级目录。
3. 仅当目标就是独立仓根时，再检查 `<target>/tests/test-system.json`

候选位置中同时存在多份合同不会自动选一份，而是阻断并要求显式指定。`release` 和 `installed` 载体不做测试体系判断；应回到权威源码运行。

Git 仓使用 tracked 文件和当前未忽略的 untracked 文件，以便提交前发现新 runner；ignored、缓存、依赖和常见生成目录不进入盘点。审计不读取 Git 历史。

## `test-system.json` v1

合同顶层只允许以下字段：

```json
{
  "schema_version": 1,
  "skill": "demo-skill",
  "target_root": ".",
  "inventory_patterns": ["tests/test_*.py", "checks/check_*.mjs"],
  "mechanisms": [],
  "runners": [],
  "exclusions": []
}
```

- `skill` 必须等于 `SKILL.md` 的 name。
- `target_root` 是目标 Skill 相对 Git 根的位置；独立仓使用 `.`。
- `inventory_patterns` 是相对 Git 根的 glob，不允许绝对路径或 `..`。
- 所有声明路径都必须留在同一仓库根内并指向现存文件。
- 每个 pattern 命中的文件必须恰好属于一个 runner 或 exclusion。

### mechanisms

每个机制必须包含 `id`、唯一 `rule_owner`、`case_model` 和 `case_sources`：

- `none`：没有重复 case 数据，`case_sources` 必须为空。
- `inline`：少量异构场景留在测试代码；必须用 `rationale` 解释为何不适合数据化，`case_sources` 为空。
- `external`：同构 case 由外部数据拥有；`case_sources` 至少一个，且不能指向 Python、JavaScript、TypeScript 或 shell 等执行代码。

审计器只能验证这些声明和路径，不能证明 `rationale` 的业务判断正确；Agent 仍需阅读代表文件复核。

### runners

每个 runner 必须包含：

- `id`：稳定标识。
- `boundary`：由源仓命名的执行边界，如 `unit`、`browser`、`release`、`windows`。
- `mode`：`shared` 或 `standalone`。
- `command`：人类可复核的统一入口；静态审计不会运行它。
- `files`：属于这个执行单元的文件，可以有多个测试模块。
- `covers`：覆盖的 mechanism id。

同一 mechanism 与 boundary 只能有一个 shared runner。`standalone` 必须额外声明 `owner`、`reason` 和 `exit_condition`；它表示已知且受治理的独立生命周期，不是绕过共享 runner 的快捷方式。

### exclusions

`inventory_patterns` 命中但不属于测试执行的文件可放入 exclusions。每项至少声明 `file` 和 `reason`，可补充 `owner` 与 `review_when`。排除项仍是可见合同，不等于忽略整个目录。

## 状态与退出码

- 没有候选测试资产：`not-applicable`，不增加 finding。
- 有候选资产但没有合同：`review` + warning，退出码仍为 `0`。
- 合同存在且引用、覆盖和边界闭环：`pass`。
- 已采用合同后 schema 无效、文件断链、漏登记、重复归属、重复共享边界或越界引用：`fail` + error，退出码为 `1`。
- 参数、目标路径或审计器自身运行失败仍使用退出码 `2`。

`pass` 只说明源仓声明与当前静态文件一致，不等于真实测试已执行，也不等于测试内容正确。真实结果仍归 `runtime_verification` 和代表任务验收。

## 源仓优化顺序

发现膨胀风险后，在目标源仓而不是 `skill-optimizer` 中处理：

1. 先把同一失败机制的规则收敛到唯一 owner。
2. 再把重复环境启动收敛为共享 runner 或 fixture。
3. 把同构变化迁为参数化数据；保留不同机制的独立断言模块。
4. 把无法合并的执行入口登记为 standalone，并设置退出条件。
5. 先迁移覆盖、再删除旧入口，使用源仓自己的命令与真实任务验证。

不得为了通过合同把大量不同机制塞进一个不可维护的大文件，也不得把未登记文件简单加入 exclusions 掩盖问题。

# Skill 源码与发行合同

本仓库把三个角色分开：

1. **权威源码**：开发者修改、测试和维护的唯一位置。
2. **发行载荷**：用户安装后真正需要的 `SKILL.md`、`agents/`、`scripts/`、`references/`、`assets/`，以及随包交付的精简 `README.md` 和 `LICENSE`。
3. **安装副本**：从发行载荷复制到 `~/.codex/skills/`、`~/.claude/skills/` 或其他 Agent 发现目录的实体快照，不使用软链，也不作为反向覆盖源码的依据。

## 权威边界

- `wise-image-flow` 的唯一权威源码是同级独立仓库 `../wise-image-flow`。本仓库中的同名目录是受管的实体发行镜像，禁止手改。
- 其余 Skill 的权威源码就是本仓库中的同名目录。
- `docs/`、`tests/`、仓库级脚本和展示素材属于开发仓，不进入单个 Skill 用户包；展示材料必须从仓库 README 或文档索引可达。
- `optimize-system-performance` 继续作为远端仓库中的独立旧 Skill 保留；本机不再安装它。`mac-cleanup` 是本机当前入口，两者不得用本机安装副本相互覆盖源码。

每个可安装 Skill 目录必须携带人类可读的精简 `README.md`，以及与仓库根一致的 `LICENSE`。完整发行包根目录使用 `docs/release-README.md` 生成精简 `README.md`，并同时携带根 `LICENSE`；不会把展示大图和开发文档复制进运行载荷。

Python 测试和审计产生的 `__pycache__`、`.pyc` 与 `.DS_Store` 是可重建缓存，`check` 与 `build` 必须一致忽略；`tests/`、备份文件、发布元数据和其他开发内容仍必须阻断发行。

机器上的个人状态不进入公开发行包。`mac-cleanup` 默认把个人档案放在 `~/.local/share/mac-cleanup/known-state.md`，Skill 内只带无个人数据的初始化模板。

## 固定命令

从外部权威源码更新发行镜像：

```bash
python3 scripts/manage_release.py sync
```

只读检查源码/发行边界及镜像漂移：

```bash
python3 scripts/manage_release.py check --require-external
```

在一个不存在或为空的目录生成干净发行包：

```bash
python3 scripts/manage_release.py build --output /absolute/path/to/release
```

发布前至少运行：

```bash
python3 scripts/manage_release.py check --require-external
python3 -m unittest discover -s tests -p 'test_*.py'
```

`skills-release.json` 是发行 Skill 清单。未列入清单的本地归档目录不会被 `manage_release.py` 打包，也不参与数量验收。

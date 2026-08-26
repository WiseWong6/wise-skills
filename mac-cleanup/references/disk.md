# 磁盘空间 Playbook

触发：磁盘满、空间不够、「有什么可以清理的」。核心方法：从大到小分层钻取，每层只追大头。

## 钻取方法

```bash
df -h /                                                    # 总量先报：已用/可用/占用%
du -sh ~/* 2>/dev/null | sort -hr | head -20               # 家目录第一层
du -sh ~/.[^.]* 2>/dev/null | sort -hr | head -20          # ⚠️ 点开头目录必须单独查！~/* 不含它们
du -sh ~/Library/* 2>/dev/null | sort -hr | head -15       # Library 逐层钻
sudo du -sh /* 2>/dev/null | sort -hr | head               # 系统级，走交接
```

`~/*` 不包含点目录；每次都要单独检查，但不能因为体积大就直接判定为垃圾。

`~/Library` 惯犯位置：`Containers`、`Application Support`、`Caches`、`Developer`（Xcode）、`Application Support/Google`、` group containers`。

## 惯犯清单（按优先级查）

| 类别 | 位置 | 清法 |
|---|---|---|
| 包管理缓存 | `~/.cache/uv`、`~/.npm`（含 `_npx`）、`~/Library/pnpm`、pip 缓存、`brew cleanup` | 基本无风险，用各官方 clean 命令；被占用不强删 |
| Xcode | `~/Library/Developer/Xcode/{iOS DeviceSupport,DerivedData,UserData/Previews}`、模拟器 `xcrun simctl delete` + 设备数据 | 官方命令优先 |
| AI CLI 会话归档 | `~/.codex`、`~/.claude`、`~/.kimi` 等的 sessions/archives | 按日期窗口（默认留 30 天） |
| 应用缓存 | `~/Library/Caches/*` | 按应用逐个看，运行中的应用跳过 |
| 项目垃圾 | node_modules（项目已死）、.venv、重复构建产物、渲染帧/中间帧 | 查项目是否还活跃再删 |
| 下载目录 | DMG/zip 安装包 | 列出来让用户过目 |
| 废纸篓 | `~/.Trash` | **只列内容，用户过目后才清** |

## 散落文件盘点（家目录/桌面）

用户习惯把东西堆在家目录根。逐个 `ls -la` + 查修改时间 + 问用途，按四种命运分类：删（垃圾/备份文件）、归并挪走（文档类→Documents、工具→Projects/scripts）、留、问用户。挪动方案先列清单，用户说"执行"再动。

## 判重与取证

- 重复目录：抽样哈希或 `diff -r` 校验，确认内容相同才去重，并先让用户选择保留版本。
- 不明目录：查内容（配置文件里的用户名/CDN 域名/token）、修改时间、是否被引用（zshrc、软链、项目 .env）。身份不明就联网查。
- root 属主文件删不动：收集路径走 sudo 交接，用户跑完复查。

## 报告

按 SKILL.md 报告契约四层分类输出，每项带来源/风险/建议。跟踪磁盘数字：战役开始记录可用空间，每轮执行后用 `df -h /` 汇报实际增量。

## 磁盘满的紧急顺序

先删纯缓存止血（uv/npm/npx/Caches），再处理需确认项。系统盘 >95% 时优先推荐①层，快速释放。

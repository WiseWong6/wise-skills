# CLI 工具/包管理器 Playbook

触发：盘点 cli、npm/brew/pip 有没有用、更新、卸载、「乱七八糟的东西」。

## 盘点命令（全量）

```bash
# Homebrew
brew leaves                    # 主动装的
brew list --formula --versions
brew list --cask --versions
brew outdated                  # 联网慢，后台跑
brew services list             # 服务型包（另见 startup.md）

# Node
npm ls -g --depth=0
du -sh ~/.npm ~/.npm/_npx      # npx 缓存可能占用较大空间
which -a node npm npx          # 重复安装检测

# Python
pip3 list --user 2>/dev/null; pipx list 2>/dev/null; uv tool list 2>/dev/null
which -a python3 pip3 uv

# 其他
gem list --user-install 2>/dev/null; cargo install --list 2>/dev/null; composer global show 2>/dev/null
```

## 重复安装处理

1. `which -a <cmd>` + `echo $PATH` 查哪套在实际使用（PATH 靠前的赢）。
2. 每套查清依赖方和实际入口再决定去留；被其他工具依赖的运行时不能单独卸载。
3. 删旧套用官方卸载（brew uninstall / 官方 uninstall 脚本），不手删目录。

## 逐包解释（用户明确要求过）

过期/可疑包逐个列表：**是什么、干嘛的、为什么装着、要不要动**。用户不懂的（"pip什么的我不太懂"）更要解释清楚。

## 更新规则（反对笼统升级）

- **不跑 `npm update -g`**：会把装得比 registry latest 还新的包（本地 dev 版）降级。
- 逐包点名升级：`npm install -g <pkg>@latest`，先比对 `npm view <pkg> version`。
- 比最新版还新的包：保持不动并说明。
- `brew upgrade` 涉及大版本变化时单独提示兼容风险。

## 删除规则

- `brew uses --installed <formula>` 查有无依赖再删，并在执行前说明包管理器可能连带移除的依赖。
- npm 全局包：`npm uninstall -g <pkg>`。
- npx 缓存 `~/.npm/_npx`：整删安全，下次用自动重下；被运行中 MCP 占用则延后。
- cask 记录与实际文件不一致时，先查安装收据和官方卸载方式，再决定是否用 `brew uninstall --cask` 清理记录。

## sudo 交接（惯犯）

`/usr/local/bin` 下的坏链接、`/usr/local/lib/node_modules` 下的 root 属主残留 → 收集路径，一条条列进交接命令。

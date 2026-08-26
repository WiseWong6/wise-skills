# 应用盘点 Playbook

触发：盘点应用、删应用、「有哪些能清理的」。

## 盘点命令

```bash
# 体积排序
du -sh /Applications/*.app 2>/dev/null | sort -hr | head -40

# 最近使用时间（判断用不用的关键依据）
mdls -name kMDItemLastUsedTime -name kMDItemUseCount /Applications/<App>.app

# 安装日期
mdls -name kMDItemDateAdded /Applications/<App>.app

# 数据残留大户
du -sh ~/Library/Containers/* 2>/dev/null | sort -hr | head -15
du -sh ~/Library/"Application Support"/* 2>/dev/null | sort -hr | head -15
```

## 判据

- **Spotlight 使用记录**比"装没装"重要：`kMDItemLastUsedTime` 很久远/缺失 + UseCount 低 = 候选；注意点目录和 CLI 工具没有记录属正常。
- **迁移陷阱**：如果机器做过迁移，一批应用可能拥有相同的迁移日期；安装日期不代表最近是否使用，应结合 Spotlight 使用记录和个人档案判断。
- **孤儿容器**：`~/Library/Containers/<bundleid>` 存在但对应应用不在 /Applications = 已卸载应用的残留数据，直接列为可清。
- 同类应用是否合并必须逐个确认用途和最近使用时间，不能只按数量删减。
- 数据目录身份不明（如 `@hilo`）：读里面的配置/登录令牌/CDN 域名确认归属和最后使用时间，**确认是活跃应用的数据就绝不单独删**，只能"应用+数据一起删"作为选项给用户。

## 删除执行

1. 用户点名具体应用后，优先使用应用自带卸载器或系统废纸篓；只有确认无卸载器且属主是当前用户时，才把明确的 `.app` 目标移到废纸篓。
2. **App Store 应用属主是 root**，rm 会失败：改用 Finder/系统弹授权窗的方式（把 .app 挪到废纸篓触发管理员授权弹窗，用户输密码）。
3. 本体删完后扫残留并顺手清：`~/Library/Preferences/<bundleid>*`、`~/Library/Containers/<bundleid>`、`~/Library/Application Support/<name>`、Caches、Saved Application State。
4. 汇报释放量。

## 误报排除

按名字 grep 时注意子串误报：`systemuiserver` 含 "temu"、`Inssist` 含 "ssis" 之类。删前核对 bundle ID 归属。

## 应用内数据（只指引不代删）

微信/企业微信的聊天文件、Chrome 的 Service Worker 缓存、浏览器的配置文件——列大小，指明正确清理路径（微信：设置→通用→存储管理；Chrome：设置→清除浏览数据只勾缓存），或"退出应用后我来删目录"作为二选一。

报告末尾对照外部个人档案：已确认在用的应用不进清理建议。

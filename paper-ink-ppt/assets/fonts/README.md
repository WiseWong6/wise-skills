# 字体说明

paper-ink-ppt skill 依赖 5 个本地开源字体，字形是纸墨线稿风的视觉根基。
字体文件（共约 79MB）**不进 git**，避免仓库膨胀。首次使用时由
`download-fonts.sh` 从官方源自动下载。

## 快速就绪

```bash
bash download-fonts.sh
```

脚本会逐个检测：已存在且非空的字体跳过，缺失的才下载。幂等，可反复执行。
强制重下（用于校验/修复）：`bash download-fonts.sh --force`。

## 字体清单

| 本地文件名 | 字体 | 字重 | 用途 | 协议 |
|---|---|---|---|---|
| `SourceHanSerifCN-Medium.otf` | 思源宋体 CN | 500 | 大字标题、金句、结论 | SIL OFL 1.1 |
| `SourceHanSansCN-Light.otf` | 思源黑体 CN | 300 | 正文、说明、标签 | SIL OFL 1.1 |
| `SourceHanSansCN-Regular.otf` | 思源黑体 CN | 400 | 正文（小字）、UI | SIL OFL 1.1 |
| `CourierPrime-Regular.ttf` | Courier Prime | 400 | 编号、图题、刻度、页脚 | SIL OFL 1.1 |
| `LXGWWenKai-Regular.ttf` | 霞鹜文楷 | 400 | 手写批注、引用大字 | SIL OFL 1.1 |

全部为 **SIL Open Font License 1.1**，可免费商用。

## 关于 SC / CN 命名

思源字体早期叫 `SC`（简体）/ `TC`（繁体），后改 `CN`/`TW`/`HK`。
本 skill 统一采用官方仓库当前的 **`CN` 命名**（`SourceHanSerifCN-*`），
与 `shared.css` 的 `@font-face` 引用保持一致。`SC` 与 `CN` 字形完全相同。

## 下载源

均为官方/权威仓库：

- 思源宋体：https://github.com/adobe-fonts/source-han-serif （SubsetOTF/CN/）
- 思源黑体：https://github.com/adobe-fonts/source-han-sans  （SubsetOTF/CN/）
- Courier Prime：https://github.com/google/fonts （ofl/courierprime/）
- 霞鹜文楷：https://github.com/lxgw/LxgwWenKai （fonts/TTF/）

若上游路径变动导致下载失败，请到对应仓库查最新路径并更新 `download-fonts.sh`。

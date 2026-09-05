# 地标建模与光效 · Build Landmark Model Lighting

根据真实图片和公开资料重建真实建筑与地标：调研素材 → 冻结简报 → 白模建模 → 白模校对 → 真实材质与光效 → 证据封印验证，最终交付语义化 GLB 资产和带交互的 Three.js 浏览器预览页。

## 能力

- **真实资料驱动**：身份、尺度、轮廓、结构和隐藏面由业主/建筑师/政府等权威来源决定，生图只决定构图、材质气质和光效语言，不用生图补造事实。
- **白模先行**：`blockout → macro → meso → micro` 逐级建模并同视口校对，白模不通过前不进入材质。
- **三类光效**：`color`（通用默认）、`build`（竖向生长）、`edge-color`（桁架/骨架拓扑寻光），按结构自动选型，每种独立过门禁。
- **证据封印**：任何 `passed` 都绑定真实 GLB/图片、当前源码哈希、本轮报告和 HTTP 返回字节；交付明确区分 `candidate-ready` 与 `visual-approved`。
- **动效门禁**：暂停/回放/模式切换/后台恢复都必须通过连续帧验收，单帧正确不算通过。

## 快速开始

初始化一个建模交付合同（不覆盖已有合同）：

```bash
python3 scripts/init_case.py \
  --root ./cases/ping-an-finance-center \
  --subject "平安金融中心" \
  --slug ping-an-finance-center \
  --effect auto \
  --review-mode user-self-check
```

交付前运行证据封印与严格校验：

```bash
python3 scripts/seal_evidence.py --root ./cases/ping-an-finance-center
python3 scripts/validate_case.py --root ./cases/ping-an-finance-center --strict
```

脚本只依赖 Python 标准库。方向图生成只使用 Codex 宿主内置 `image_gen.imagegen`，不需要第三方图片 API Key。

完整阶段门禁、接口和失败信号见 [SKILL.md](SKILL.md) 与 [references/](references/)。

License: [MIT](LICENSE) © 2026 Wise Wong

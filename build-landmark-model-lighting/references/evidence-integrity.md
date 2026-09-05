# 建模证据完整性

## 1. 三种状态

- `candidate-ready`：当前 GLB 字节、确定性源码、运行时、Khronos、loader、浏览器交互和 HTTP 返回字节已绑定并通过；视觉身份仍交给用户自检。
- `visual-approved`：用户或明确授权的 Reviewer 已按真实来源复核七视角，并留下与当前资产哈希一致的结论。
- `delivered`：`visual-approved` 之后完成范围审计、清理和交付说明。没有视觉批准时不得写 `delivered`。

默认采用 `user-self-check`。除非用户明确要求截图或视觉验收，不创建成套 raster captures，不让 Builder 自己把主观判断写成 `pass`。

## 2. 证据图

严格交付按下面的单向关系绑定：

`真实来源 + ModelBrief + DirectionSet → 建模源码 → GLB → 运行时 → Khronos/loader/browser → evidence seal`

以下任一内容变化，旧封印立即失效：

- 真实来源、本地参考文件或冻结简报；
- 方向图、确定性建模源码、GLB；
- 运行时、acceptance bridge、验证驱动；
- Khronos、loader、browser 或视觉比较报告。

不得通过手改报告哈希、复制旧截图、改文件名或复用旧 `passed` 解除失效。重新运行验证，再生成新封印。

## 3. 同轮封印

完成机器检查后运行：

```bash
python3 <skill-dir>/scripts/seal_evidence.py --root <case-root>
python3 <skill-dir>/scripts/validate_case.py --root <case-root> --strict
```

封印必须记录：

- 唯一 `run_id` 与 UTC 时间；
- GLB、源码、运行时、简报、来源、方向集和三个验证报告的路径、SHA-256 与字节数；
- 当前 Git HEAD 和案例路径内的 dirty files；
- Khronos `validatorVersion / validatedAt / mimeType / uri`；
- loader 与 browser 的本轮时间、当前资产 SHA；
- 浏览器从 HTTP 实际收到的 GLB SHA，而不是只记录请求成功。

`seal_evidence.py` 默认拒绝超过 24 小时的验证报告。需要更长窗口时显式传 `--max-age-hours` 并在交付风险中解释。

## 4. 机器可拒绝的最低真实性

严格校验必须直接读取原始字节：

- GLB 具有 `glTF` magic、container version 2、正确总长度和合法 JSON chunk；
- PNG/JPEG/WebP 必须有真实文件签名和正尺寸，不能用任意文本冒充截图；
- DeliveryManifest 的 `bytes` 与磁盘文件一致；
- 每个报告文件哈希与 evidence seal 一致；
- Khronos 报告指向当前 GLB 文件名且 error 为 0；
- loader/browser 报告的资产 SHA 与当前 GLB 一致；
- browser 的 HTTP 字节 SHA 与当前 GLB 一致。

这些门禁只能证明证据链自洽，不能证明建筑视觉正确。视觉正确仍由真实来源对照和人工验收决定。

## 5. 历史失败模式对应门禁

| 失败信号 | 根因 | 系统门禁 |
| --- | --- | --- |
| GLB 换了仍沿用旧截图/报告 | 证据没有绑定当前字节 | 变更即失效；同轮封印校验全部哈希 |
| HTTP 200 或单张截图被写成完成 | 可达性替代交互与连续帧 | browser 报告必须覆盖暂停、replay、模式切换、visibility 和 HTTP SHA |
| 结构脚本全绿但建筑不像 | 文件正确性替代视觉身份 | `candidate-ready` 与 `visual-approved` 分层 |
| Reviewer 中断仍被当作 pass | 任务状态替代结果文件 | 只有存在当前哈希的 review evidence 才能 visual-approved |
| 透视照片做像素 overlay | 相机未标定 | 只做语义/比例人工判断，不给伪精确像素结论 |
| 未知材质被品牌色或发光覆盖 | 视觉效果掩盖事实缺口 | 未知区保持中性并登记 |
| 在脏工作树里全量暂存 | 交付范围与并行工作混合 | 按路径审计和暂存；封印记录案例 dirty paths |
| 路径重复导致打包找错目录 | 工作目录与参数语义不清 | 所有交付命令从案例根或仓库根执行，并输出绝对解析路径 |

## 6. 旧案例

旧 schema 可用以下命令诊断迁移缺口：

```bash
python3 <skill-dir>/scripts/validate_case.py \
  --root <legacy-case-root> \
  --strict \
  --allow-legacy-evidence
```

该模式必须产生 legacy warning，不能作为“当前证据已封印”或 `visual-approved` 的依据。

# Memory Fragment Posters · 记忆碎片摄影海报

<p align="center">
  <strong>简体中文</strong> · <a href="README_EN.md">English</a>
</p>

<p align="center">
  <a href="https://github.com/WiseWong6/memory-fragment-posters/blob/main/LICENSE"><img src="https://img.shields.io/github/license/WiseWong6/memory-fragment-posters?style=for-the-badge" alt="MIT License"></a>
  <a href="https://github.com/WiseWong6/wise-skills"><img src="https://img.shields.io/badge/More-Wise%20Skills-173F5F?style=for-the-badge" alt="Wise Skills"></a>
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#两套版本">两套版本</a> ·
  <a href="#精确对应的制作方式">制作方式</a> ·
  <a href="#输出与验收">输出与验收</a>
</p>

从每张照片里取下一块记忆，放到暖象牙纸上，再把所有记忆拼成一张完整海报。

**记忆碎片摄影海报**是为 Codex 封装的摄影排版技能。助手阅读照片、选择有辨识度的局部，专用程序按坐标裁取原照内容。上方碎片、下方缺口和最终拼接共用同一份照片裁片与形状遮罩，保留原来的颜色、透视与光影。

默认交付**拼图版 + 票根版**：每套包含每张照片的独立海报，以及一张完整拼接图。上传 9 张照片，得到两套共 **20 张**。

## 效果预览

以下为作者授权公开的定稿成品。左右分别为拼图版与票根版，点击可查看原尺寸。示例只用于理解设计，不作为新任务的照片输入。

<table>
  <tr><th>拼图版</th><th>票根版</th></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/10.png"><img src="assets/examples/puzzle/10.png" alt="完整拼接 · puzzle" width="100%" loading="lazy"></a><br>完整拼接</td><td width="50%"><a href="assets/examples/ticket/10.png"><img src="assets/examples/ticket/10.png" alt="完整拼接 · ticket" width="100%" loading="lazy"></a><br>完整拼接</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/01.png"><img src="assets/examples/puzzle/01.png" alt="雪山与海 · puzzle" width="100%" loading="lazy"></a><br>雪山与海</td><td width="50%"><a href="assets/examples/ticket/01.png"><img src="assets/examples/ticket/01.png" alt="雪山与海 · ticket" width="100%" loading="lazy"></a><br>雪山与海</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/02.png"><img src="assets/examples/puzzle/02.png" alt="黄金岁月 · puzzle" width="100%" loading="lazy"></a><br>黄金岁月</td><td width="50%"><a href="assets/examples/ticket/02.png"><img src="assets/examples/ticket/02.png" alt="黄金岁月 · ticket" width="100%" loading="lazy"></a><br>黄金岁月</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/03.png"><img src="assets/examples/puzzle/03.png" alt="夕阳的机翼 · puzzle" width="100%" loading="lazy"></a><br>夕阳的机翼</td><td width="50%"><a href="assets/examples/ticket/03.png"><img src="assets/examples/ticket/03.png" alt="夕阳的机翼 · ticket" width="100%" loading="lazy"></a><br>夕阳的机翼</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/04.png"><img src="assets/examples/puzzle/04.png" alt="南京陵园路 · puzzle" width="100%" loading="lazy"></a><br>南京陵园路</td><td width="50%"><a href="assets/examples/ticket/04.png"><img src="assets/examples/ticket/04.png" alt="南京陵园路 · ticket" width="100%" loading="lazy"></a><br>南京陵园路</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/05.png"><img src="assets/examples/puzzle/05.png" alt="杭州机场 · puzzle" width="100%" loading="lazy"></a><br>杭州机场</td><td width="50%"><a href="assets/examples/ticket/05.png"><img src="assets/examples/ticket/05.png" alt="杭州机场 · ticket" width="100%" loading="lazy"></a><br>杭州机场</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/06.png"><img src="assets/examples/puzzle/06.png" alt="海上日落 · puzzle" width="100%" loading="lazy"></a><br>海上日落</td><td width="50%"><a href="assets/examples/ticket/06.png"><img src="assets/examples/ticket/06.png" alt="海上日落 · ticket" width="100%" loading="lazy"></a><br>海上日落</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/07.png"><img src="assets/examples/puzzle/07.png" alt="阔叶树枝梢 · puzzle" width="100%" loading="lazy"></a><br>阔叶树枝梢</td><td width="50%"><a href="assets/examples/ticket/07.png"><img src="assets/examples/ticket/07.png" alt="阔叶树枝梢 · ticket" width="100%" loading="lazy"></a><br>阔叶树枝梢</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/08.png"><img src="assets/examples/puzzle/08.png" alt="招牌人物 · puzzle" width="100%" loading="lazy"></a><br>招牌人物</td><td width="50%"><a href="assets/examples/ticket/08.png"><img src="assets/examples/ticket/08.png" alt="招牌人物 · ticket" width="100%" loading="lazy"></a><br>招牌人物</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/09.png"><img src="assets/examples/puzzle/09.png" alt="雪夜街角 · puzzle" width="100%" loading="lazy"></a><br>雪夜街角</td><td width="50%"><a href="assets/examples/ticket/09.png"><img src="assets/examples/ticket/09.png" alt="雪夜街角 · ticket" width="100%" loading="lazy"></a><br>雪夜街角</td></tr>
</table>

## 核心能力

- **自动选取记忆点**：助手根据照片选择雪山、枝梢、落日、人物或建筑细节，直接制作；用户指定的位置优先。
- **原照精确裁切**：处理照片方向后等比取景，不重绘、不补画、不拉伸，也不另加调色滤镜。
- **上下严格等分**：1800×2400 像素，纸面与摄影各占 1200 像素，直接衔接。
- **三处共用裁片**：上方碎片、下方缺口和最终拼接使用同一坐标与轮廓，最终只平移。
- **真正互补咬合**：整批照片先规划共享边界，再提取碎片，组合连续且没有内部空洞。
- **不覆盖历史成果**：已有同名目录时另建版本，全部检查通过才发布本批结果。

## 两套版本

| | 拼图版 | 票根版 |
|---|---|---|
| 轮廓 | 圆形凸榫与互补凹槽 | 互补齿孔，外围齿孔向内 |
| 基础单元 | 390×390 像素 | 420×320 像素 |
| 单张海报 | 上半暖纸与小碎片，下半原照与原位缺口 | 同左 |
| 最后一张 | 全部碎片拼成完整主体，暖纸留白 | 同左 |

照片较多时，提取前统一缩小整套轮廓，使组合宽度不超过画布的 70%、高度不超过 60%。最终拼接直接复用裁片，不再改变大小或方向。

整体采用暖象牙纤维纸、细微颗粒和克制留白。没有新增文字、标志、水印、贴纸、胶带或厚重阴影；照片里原有的招牌和文字保留。

## 安装

需要 Python 3、Pillow 和 NumPy，以及能够阅读照片、执行本地脚本的 Codex 环境。脚本不会自动安装依赖；缺少依赖时会明确报错。

```bash
git clone https://github.com/WiseWong6/memory-fragment-posters.git \
  ~/.codex/skills/memory-fragment-posters
```

如果环境通过 `~/.agents/skills` 发现技能，可在目标不存在时建立同源入口：

```bash
mkdir -p ~/.agents/skills
ln -s ~/.codex/skills/memory-fragment-posters \
  ~/.agents/skills/memory-fragment-posters
```

已有安装时先检查目录，避免覆盖。更新使用：

```bash
git -C ~/.codex/skills/memory-fragment-posters pull --ff-only
```

本技能也收录在 [Wise Skills](https://github.com/WiseWong6/wise-skills)。入口设置 `allow_implicit_invocation: false`，仅在明确点名或主动选择后执行。

## 快速开始

在 Codex 中附上原始照片，然后调用：

```text
用 $memory-fragment-posters 处理这些照片，生成拼图版和票根版。
```

只制作一种版本：

```text
用 $memory-fragment-posters 处理这些照片，只要拼图版。
```

指定记忆点：

```text
用 $memory-fragment-posters 制作这组照片。
海边照片取远处雪山，树木照片取树尖或树杈边缘，其余自动选择。
```

默认自动取景并直接制作。需要先看候选时，可以在调用中明确提出。

## 精确对应的制作方式

1. 助手阅读原照，选择记忆点，确定原图内的 3:2 横幅取景框与碎片中心。
2. 程序处理照片方向，以等比取景铺满海报下半区。
3. 根据照片总数规划接近方形的连续排列，相邻碎片共享同一条边界。
4. 从下半区照片提取一次裁片和遮罩，将同一裁片移到上半区，在原坐标填入纸面。
5. 最终拼接只移动这些裁片，不单独缩放、旋转或重新取景。
6. 对保存结果逐像素检查，包含边缘半透明像素；失败的批次不会成为正式交付。

**选取内容由助手完成；脚本负责确定性排版，没有独立的语义识别模型。** 整个制作程序无需网络、图片接口或密钥。宿主必须允许这类原照片处理；本技能不授予绕过宿主规则的权限。

### 手动运行

在仓库目录下查看方向校正后的尺寸：

```bash
python3 scripts/render.py inspect /absolute/path/photo.jpg
```

按 [输入说明](references/input.md) 编写配置，再执行：

```bash
python3 scripts/render.py render \
  --config /absolute/path/config.json \
  --output /absolute/path/outputs/记忆碎片摄影海报
```

配置记录照片顺序、路径、原图裁切框、碎片中心和所需版本。不要把个人照片路径提交到仓库。

## 输出与验收

以 9 张照片为例：

```text
outputs/记忆碎片摄影海报/
├── 拼图版/
│   ├── 01_照片名称.png
│   ├── …
│   ├── 09_照片名称.png
│   └── 10_完整拼接.png
├── 票根版/
│   ├── 01_照片名称.png
│   ├── …
│   ├── 09_照片名称.png
│   └── 10_完整拼接.png
└── 制作检查.json
```

每张 PNG 均为 1800×2400。单张海报上下严格各半；最终拼接图为整张纸面与完整拼图。目标目录已存在时，自动使用 `-v2`、`-v3` 等新目录。

检查覆盖尺寸、裁片像素、原位缺口、形状互补、半透明边缘、整体连通和内部空洞。报告状态为 `complete` 才表示该批程序检查完成；取景的审美选择仍以用户判断为准。

运行回归检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_render.py
```

测试覆盖 1、2、5、10 张排列，以及竖图、照片旋转、主体靠边、中文文件名、缺失文件、重复目录和失败不发布。测试素材临时生成，结束后自动清理。

## 已知边界

- 竖图放入横幅区域需要自然裁切，不能同时保留原图全部环境。
- 碎片中心靠边时，来源框会整体移入照片，实际位置记录在检查报告里。
- 不接受动画或多帧图片，包括部分使用 JPG 扩展名的 MPO 文件；需先提供确定的静态主图。
- 不支持任意画幅或单独缩放某块碎片，以保证三个位置精确对应。
- 不重绘、扩图、补画或调用第三方生图服务。仓库仅包含作者授权公开的定稿示例，不包含原始照片、私人路径或任务记录。

## 关于作者

全网同名 **@歪斯Wise**，持续分享 AI 创作、Agent 工作流、视觉设计与效率工具。

[X / Twitter](https://x.com/killthewhys) · [小红书](https://www.xiaohongshu.com/user/profile/61f3ea4f000000001000db73) · [Wise Skills](https://github.com/WiseWong6/wise-skills)

<p><img src="assets/social/xiaohongshu-qr.jpg" width="180" alt="歪斯Wise 小红书名片"></p>

## 许可证

[MIT](LICENSE) © 2026 Wise Wong。许可证适用于技能代码与文档；示例成品及使用者提供的照片仍归其各自权利人所有，不随代码的 MIT 许可转授权。

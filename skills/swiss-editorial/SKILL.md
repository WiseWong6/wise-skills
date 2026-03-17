---
name: swiss-editorial
description: 将 Markdown 转换为 600x800px 杂志风信息海报（Swiss Style + Modern Editorial），支持封面+正文多卡片输出
---

# swiss-editorial

社论风 HTML 排版工具：一个 Web 实时预览工具，将 Markdown 内容转化为 600x800px 杂志风信息卡片。

## 快速开始

```bash
# 方式1：直接用浏览器打开
open ~/.claude/skills/swiss-editorial/public/index.html

# 方式2：用 Python 简易服务器
python3 -m http.server 8080 -d ~/.claude/skills/swiss-editorial/public
# 然后访问 http://localhost:8080
```

## 使用方式

1. 左边输入 Markdown
2. 右边实时预览
3. 用 `---` 分隔不同卡片
4. 第一张 `---` 之前的内容自动成为封面（米白背景）

## 风格定义

### 尺寸与容器
- **尺寸**: `width: 600px`, `height: 800px` (3:4)
- **容器类名**: `swiss-card`
- **圆角**: 强制 `border-radius: 0`

### 配色方案 (Scheme K - Hermès)

**封面模式**
| 元素 | 色值 |
|------|------|
| 背景 | `#f2efe9` (米白) |
| 文字 | `#1a1a1a` |
| 强调 | `#d95e00` (爱马仕橙) |

**正文模式**
| 元素 | 色值 |
|------|------|
| 背景 | `#ffffff` (纯白) |
| 文字 | `#1a1a1a` |
| 强调 | `#d95e00` |

### 设计原则
- **Modern Editorial** + **Swiss Style**
- 秩序感、高对比、纸媒质感
- 充足呼吸感，避免信息堆砌

## 样式规则

### 标题
- `h1`: 封面标题，48px，Noto Serif SC，700 字重
- `h2`: 章节标题，32px，底部 3px 橙色边框
- `h3`: 小标题，22px，橙色

### 正文
- 字号: 16px
- 字重: 300 (light)
- 行高: 2.0
- 对齐: justify

### 加粗与强调
- `**加粗**` → `<strong>` + 橙色
- `*强调*` → `<em>` + 橙色斜体

### 引用块
- 左侧 4px 橙色边框
- 淡橙色背景 `rgba(217, 94, 0, 0.05)`
- 斜体正文

### 代码块
- 深色背景 `#1a1a1a`
- 浅色文字 `#f2efe9`
- 等宽字体 SF Mono / Monaco / Menlo
- 圆角强制为 0

### 链接
- 橙色 + 下边框
- hover 时透明度变化

### 分割线
- 橙色
- 宽度 60px
- 左侧对齐

## 快速开始

```bash
python3 ~/.claude/skills/swiss-editorial/scripts/convert_md_to_swiss.py input.md -o output.html
```

### 输入格式

```markdown
# 封面标题

---

## 第一章

正文内容...

---

## 第二章

更多内容...
```

- `---` 之前的内容 → 封面卡片
- `---` 之间的内容 → 多个正文卡片

## 示例

```markdown
# 设计之道

---

## 极简主义

Less is more。少即是多，是设计的基本原则。

**核心原则**：
- 去除多余装饰
- 保留本质功能
- 追求纯粹形式

> 设计不是为了填充，而是为了表达。
```

## 布局组件

### 布局分类体系

| 类别 | 用途 | 组件 |
|------|------|------|
| **对比类** | 展示对立/差异 | vs-grid, before-after, swot |
| **流程类** | 展示步骤/顺序 | process-chain, process-loop, journey, gantt |
| **层级类** | 展示层次关系 | concentric, timeline, bridge |
| **结构类** | 展示组成结构 | pyramid, funnel, fishbone, iceberg, venn |
| **展示类** | 数据/信息展示 | stat-card, radar, list-card, matrix-grid |
| **特殊类** | 特定场景 | title-card, quote, alert-box, terminal-box |

---

### 1. 对比类布局

#### 1.1 VS 对比 (.vs-grid)
左右对比布局，用于展示两种方案/观点的对比。

```html
<div class="vs-grid">
    <div>
        <strong>方案A</strong>
        <p>优势描述...</p>
    </div>
    <div class="vs-divider">VS</div>
    <div>
        <strong>方案B</strong>
        <p>优势描述...</p>
    </div>
</div>
```

#### 1.2 前后对比 (.before-after)
展示改进前后的对比，支持带箭头模式。

```html
<!-- 基础版 -->
<div class="before-after">
    <div class="side before">
        <span class="badge">BEFORE</span>
        <p>改进前...</p>
    </div>
    <div class="side after">
        <span class="badge">AFTER</span>
        <p>改进后...</p>
    </div>
</div>

<!-- 带箭头版 -->
<div class="before-after with-arrow no-bg">
    <div class="side before">
        <span class="badge">现状</span>
        <p>日活：1万</p>
    </div>
    <div class="arrow">→</div>
    <div class="side after">
        <span class="badge">目标</span>
        <p>日活：10万</p>
    </div>
</div>
```

#### 1.3 SWOT 分析 (.swot)
四象限分析布局。

```html
<div class="swot">
    <div class="cell strengths">
        <h4>S 优势</h4>
        <p>技术强、团队稳</p>
    </div>
    <div class="cell weaknesses">
        <h4>W 劣势</h4>
        <p>资金少、品牌弱</p>
    </div>
    <div class="cell opportunities">
        <h4>O 机会</h4>
        <p>市场大、政策好</p>
    </div>
    <div class="cell threats">
        <h4>T 威胁</h4>
        <p>竞品多、成本涨</p>
    </div>
</div>
```

---

### 2. 流程类布局

#### 2.1 流程链 (.process-chain)
线性流程展示，支持多种变体。

**基础版（3-6步骤）：**
```html
<div class="process-chain">
    <div class="step">需求</div>
    <div class="arrow">→</div>
    <div class="step">设计</div>
    <div class="arrow">→</div>
    <div class="step">开发</div>
</div>
```

**彩色箭头形状版（data-type="arrow"）：**
- 支持 3-5 步骤
- 彩虹色渐变：紫→蓝→青→绿→橙
- 首尾步骤形状特殊处理
- 文字较长时自动压缩间距和字号

```html
<div class="process-chain" data-type="arrow">
    <div class="step">智能客服</div>
    <div class="arrow">→</div>
    <div class="step">规划顾问</div>
    <div class="arrow">→</div>
    <div class="step">核保专家</div>
    <div class="arrow">→</div>
    <div class="step">理赔助手</div>
    <div class="arrow">→</div>
    <div class="step">保险智能体</div>
</div>
```

**设计要点：**
| 步骤数 | 适配方案 |
|--------|----------|
| 3-4 步骤 | 标准padding (16px 8px)，14px字号 |
| 5 步骤 | 压缩padding (16px 8px)，13px字号，nowrap |
| 6+ 步骤 | 使用 data-type="wrap" 双行显示 |

#### 2.2 循环流程 (.process-loop)
闭环流程展示，支持多种形状。

```html
<!-- 三角循环 -->
<div class="process-loop" data-type="triangle">
    <div class="loop-item">计划</div>
    <div class="loop-item">执行</div>
    <div class="loop-item">检查</div>
</div>

<!-- 四角循环 -->
<div class="process-loop" data-type="quad">
    <div class="loop-item">需求</div>
    <div class="loop-item">开发</div>
    <div class="loop-item">测试</div>
    <div class="loop-item">上线</div>
</div>

<!-- 五角循环 -->
<div class="process-loop" data-type="pentagon">
    <div class="loop-item">共情</div>
    <div class="loop-item">定义</div>
    <div class="loop-item">构思</div>
    <div class="loop-item">原型</div>
    <div class="loop-item">测试</div>
</div>
```

#### 2.3 用户旅程 (.journey)
展示用户路径的各个阶段。

```html
<div class="journey">
    <div class="path">
        <div class="point">
            <div class="label">认知</div>
            <div class="dot"></div>
        </div>
        <div class="point">
            <div class="label">考虑</div>
            <div class="dot"></div>
        </div>
        <div class="point">
            <div class="label">购买</div>
            <div class="dot"></div>
        </div>
        <div class="point">
            <div class="label">使用</div>
            <div class="dot"></div>
        </div>
        <div class="point">
            <div class="label">推荐</div>
            <div class="dot"></div>
        </div>
    </div>
</div>
```

#### 2.4 甘特图 (.gantt)
项目进度时间线。

```html
<div class="gantt">
    <div class="gantt-header">
        <div class="label">任务</div>
        <div class="timeline">
            <span>1月</span><span>2月</span><span>3月</span>
        </div>
    </div>
    <div class="task">
        <span class="task-name">需求分析</span>
        <div class="task-bar">
            <div class="fill" style="left:0%;width:30%"></div>
        </div>
    </div>
</div>
```

---

### 3. 层级类布局

#### 3.1 同心圆 (.concentric)
核心-中层-外围的层级关系。

```html
<div class="concentric align-center">
    <div class="layer layer-1">
        <span class="layer-text">核心</span>
    </div>
    <div class="layer layer-2">
        <span class="layer-text">中层</span>
    </div>
    <div class="layer layer-3">
        <span class="layer-text">外围</span>
    </div>
</div>
```

**对齐方式：**
- `.align-center` - 居中模式
- `.align-top` - 顶部对齐
- `.align-bottom` - 底部对齐

**尺寸规格：**
| 层级 | 直径 | 半径 | 文字位置 |
|------|------|------|----------|
| layer-1 | 100px | 50px | 圆心 |
| layer-2 | 180px | 90px | 70px从圆心 |
| layer-3 | 260px | 130px | 110px从圆心 |

#### 3.2 时间轴 (.timeline)
竖版或横版时间线。

```html
<!-- 竖版 -->
<div class="timeline" data-type="vertical">
    <div class="item">
        <div class="year">2024 Q1</div>
        <p>产品规划</p>
    </div>
    <div class="item">
        <div class="year">2024 Q2</div>
        <p>核心开发</p>
    </div>
</div>

<!-- 横版 -->
<div class="timeline" data-type="horizontal">
    <div class="item">
        <div class="year">Q1</div>
        <p>规划</p>
    </div>
    <div class="item">
        <div class="year">Q2</div>
        <p>开发</p>
    </div>
</div>
```

#### 3.3 桥梁 (.bridge)
从当前状态到目标状态的过渡。

```html
<div class="bridge">
    <div class="side from">
        当前问题<br/>效率低下
    </div>
    <div class="connector">→</div>
    <div class="side to">
        目标状态<br/>自动化流程
    </div>
</div>
```

---

### 4. 结构类布局

#### 4.1 金字塔 (.pyramid)
正三角或倒三角层级。

```html
<!-- 正金字塔（从大到小） -->
<div class="pyramid">
    <div class="level level-1">顶层</div>
    <div class="level level-2">第二层</div>
    <div class="level level-3">第三层</div>
    <div class="level level-4">第四层</div>
    <div class="level level-5">底层基础</div>
</div>

<!-- 倒金字塔（从上到下） -->
<div class="pyramid" data-type="inverted">
    <div class="level level-1">广泛曝光</div>
    <div class="level level-2">初步筛选</div>
    <div class="level level-3">深度考虑</div>
    <div class="level level-4">意向确认</div>
    <div class="level level-5">最终成交</div>
</div>
```

#### 4.2 漏斗 (.funnel)
转化漏斗展示。

```html
<div class="funnel">
    <div class="stage stage-1">曝光：10,000 人</div>
    <div class="stage stage-2">点击：3,000 人</div>
    <div class="stage stage-3">注册：1,000 人</div>
    <div class="stage stage-4">试用：300 人</div>
    <div class="stage stage-5">付费：100 人</div>
</div>
```

#### 4.3 鱼骨图 (.fishbone)
问题分析，展示因果关系。

```html
<div class="fishbone">
    <div class="head">问题结果</div>
    <div class="spine"></div>
    <div class="ribs ribs-top">
        <div class="rib">人员不足</div>
        <div class="rib">需求变更</div>
    </div>
    <div class="ribs ribs-bottom">
        <div class="rib">技术难题</div>
        <div class="rib">资源受限</div>
    </div>
</div>
```

#### 4.4 冰山 (.iceberg)
表面问题与深层根因。

```html
<div class="iceberg">
    <div class="above">
        <strong>表面问题</strong>
        <span>系统响应慢、界面卡顿</span>
    </div>
    <div class="waterline"></div>
    <div class="below">
        <strong>深层根因</strong>
        <span>架构设计缺陷、代码质量</span>
    </div>
</div>
```

#### 4.5 韦恩图 (.venn)
两个集合的交集展示。

```html
<div class="venn">
    <div class="circle circle-a">技术可行</div>
    <div class="circle circle-b">市场需要</div>
</div>
```

---

### 5. 展示类布局

#### 5.1 指标卡片 (.stat-card)
关键数据展示，支持趋势指示。

```html
<div class="stat-grid">
    <div class="stat-card">
        <div class="stat-card-header">
            <span class="stat-card-label">活跃用户</span>
            <span class="stat-card-trend up">+25%</span>
        </div>
        <div class="stat-card-value">
            12.5<span class="stat-card-unit">万</span>
        </div>
        <div class="stat-card-footer">
            较上月 <span class="stat-card-comparison">+2.5万</span>
        </div>
    </div>
</div>
```

**趋势样式：**
- `.up` - 上升（绿色）
- `.down` - 下降（红色）

#### 5.2 雷达图 (.radar)
多维度能力评估。

```html
<div class="radar">
    <div class="radar-title">能力评估</div>
    <div class="radar-container">
        <svg class="radar-svg" viewBox="0 0 260 260">
            <!-- 网格线 -->
            <polygon class="radar-grid" points="130,20 220,90 190,210 70,210 40,90"/>
            <!-- 数据区域 -->
            <polygon class="radar-data" points="130,35 205,95 175,195 85,195 55,95"/>
            <!-- 标签 -->
            <text class="radar-label" x="130" y="12">性能</text>
        </svg>
    </div>
</div>
```

#### 5.3 维度矩阵 (.matrix-grid)
2×2 矩阵分析。

```html
<div class="matrix-grid">
    <div class="cell">
        <h4>高价值 / 高可行</h4>
        <p>优先执行</p>
    </div>
    <div class="cell">
        <h4>高价值 / 低可行</h4>
        <p>技术突破</p>
    </div>
    <div class="cell">
        <h4>低价值 / 高可行</h4>
        <p>快速实现</p>
    </div>
    <div class="cell">
        <h4>低价值 / 低可行</h4>
        <p>暂不处理</p>
    </div>
</div>
```

#### 5.4 列表卡片 (.list-card)
美化版无序/有序列表。

```html
<!-- 无序列表 -->
<div class="list-card">
    <ul>
        <li>完成核心功能开发</li>
        <li>上线 3 个新模块</li>
    </ul>
</div>

<!-- 有序列表 -->
<div class="list-card">
    <ol>
        <li>第一步：需求分析</li>
        <li>第二步：方案设计</li>
    </ol>
</div>
```

---

### 6. 特殊类布局

#### 6.1 标题页 (.title-card)
卡片专用标题页。

```html
<div class="title-card">
    <h2>项目总结报告</h2>
    <p>2024 年度成果与展望</p>
</div>
```

#### 6.2 引用页 (.quote)
金句/名言展示。

```html
<div class="quote">
    <blockquote>"简洁是智慧的灵魂"<br/>—— 莎士比亚</blockquote>
    <cite>— 《哈姆雷特》</cite>
</div>
```

#### 6.3 警告框 (.alert-box)
重要提示信息。

```html
<div class="alert-box">
    <div class="icon">⚠️</div>
    <p>请在操作前备份重要数据</p>
</div>
```

#### 6.4 术语框 (.terminal-box)
技术术语解释。

```html
<div class="terminal-box">
    <div class="cmd">
        <span class="prompt">$</span> API - Application Programming Interface
    </div>
</div>
```

#### 6.5 架构图 (.architecture)
系统分层架构展示。

```html
<div class="architecture">
    <div class="layer">
        <div class="layer-title">应用层</div>
        <div class="modules">
            <div class="module">管理后台</div>
            <div class="module">用户端</div>
        </div>
    </div>
    <div class="layer">
        <div class="layer-title">服务层</div>
        <div class="modules">
            <div class="module">用户服务</div>
            <div class="module">订单服务</div>
        </div>
    </div>
</div>
```

---

### 7. 辅助布局

#### 7.1 多栏布局

```html
<!-- 两栏 -->
<div class="two-col">
    <div>左侧内容</div>
    <div>右侧内容</div>
</div>

<!-- 三栏 -->
<div class="three-col">
    <div>方案A</div>
    <div>方案B</div>
    <div>方案C</div>
</div>
```

#### 7.2 上下分层 (.split-v)

```html
<!-- 基础版 -->
<div class="split-v">
    <div class="top">核心结论</div>
    <div class="bottom">详细说明...</div>
</div>

<!-- 强调版 -->
<div class="split-v accent">
    <div class="top">重要提示</div>
    <div class="bottom">详细说明...</div>
</div>

<!-- 带编号 -->
<div class="split-v numbered">
    <div class="number">01</div>
    <div class="top">步骤一</div>
    <div class="bottom">详细说明...</div>
</div>
```

---

## 布局选择决策树

```
需要展示什么？
├── 对比/差异
│   ├── 两方案对比 → vs-grid
│   ├── 改进前后 → before-after
│   └── 优劣势分析 → swot
├── 流程/步骤
│   ├── 线性流程 → process-chain
│   ├── 闭环流程 → process-loop
│   ├── 用户路径 → journey
│   └── 项目进度 → gantt
├── 层级关系
│   ├── 核心-外围 → concentric
│   ├── 上下层级 → pyramid
│   ├── 时间演进 → timeline
│   └── 状态转换 → bridge
├── 组成结构
│   ├── 转化漏斗 → funnel
│   ├── 问题归因 → fishbone
│   ├── 交集关系 → venn
│   └── 显隐关系 → iceberg
├── 数据展示
│   ├── 关键指标 → stat-card
│   ├── 多维评估 → radar
│   ├── 优先级矩阵 → matrix-grid
│   └── 列表信息 → list-card
└── 特殊页面
    ├── 章节标题 → title-card
    ├── 金句引用 → quote
    └── 系统架构 → architecture
```

## 输出

生成包含 `swiss-card` 类名的 HTML 卡片，便于脚本抓取截图。

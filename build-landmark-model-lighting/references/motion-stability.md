# 动效连续性与抗闪烁合同

## 目录

1. form-atlas 问题链
2. 单一时间源与状态语义
3. 暂停、回放与后台恢复
4. Shader、透明层与深度稳定性
5. 预热、首帧与画廊切换
6. 连续帧浏览器验收矩阵
7. 报告数据合同

## 1. form-atlas 问题链

以下问题来自 `form-atlas` 的运行时和真实浏览器复现，应作为通用失败模式，而不是某个地标的个案：

1. 用户点击暂停只停止 effect progress，`OrbitControls.autoRotate` 和 damping 仍由渲染循环更新；页面看起来仍在动。
2. acceptance bridge 的冻结函数会额外关闭自动旋转和 damping。旧 QA 因而验证了比用户暂停更强的测试态，连续帧可稳定，但真实暂停不稳定。
3. replay、模式切换和 DOM 文案先更新，WebGL 画面等到下一个 RAF 才提交，会出现一帧旧状态或 UI/画布不同步。
4. 高频程序噪声、法线扰动和细线随相机缓慢旋转产生时间混叠，表现为表面颗粒、边缘或高光闪烁。
5. 与主体共面或近共面的透明 overlay、边线和扫描层参与同一深度测试；`renderOrder` 只能改变提交顺序，不能消除深度精度竞争。
6. 在阈值处直接切换 halo、局部光、阴影或裁切，会在完成态附近产生亮度突变和轮廓跳变。
7. 手写 RAF 在页面隐藏时被浏览器暂停；恢复后若沿用旧时间基线，会跳进度。没有 `visibilitychange` 生命周期时，暂停/恢复语义也不可追溯。
8. 集成画廊在旧 iframe 被移除后等待新 iframe，或把 `iframe load` 当成“真实首帧已稳定”，会暴露空白、未预热 shader 或加载样式尚未生效的帧。
9. 只检查 `0 / mid / 1` 单帧、最终稳定截图或“当前只有一个 iframe”，无法发现上述时间连续性问题。

## 2. 单一时间源与状态语义

- 每个预览只能有一个动画循环所有者。优先使用 `renderer.setAnimationLoop()`；使用 RAF 时也必须集中创建、取消并报告唯一 owner，不得在初始化、重播或 resize 时叠加循环。
- 所有自动动效都由同一个单调时间源驱动：effect progress、auto-rotate、damping、shader time、pulse、局部光和 CSS 场景动画不得各自读取互不相干的墙钟时间。
- 用 RAF 提供的 timestamp 计算 delta；不得按固定 `1/60` 累加。对恢复后的首帧只重置时间基线，不推进时间线。
- `render(effect, progress, reducedMotion, paused)` 必须是可寻址、可重复的状态函数。同一输入、相机和 viewport 在 settle 后产生同一主体画面。
- 模式切换、暂停和 replay 采用单次状态提交：先计算完整目标状态，再在同一提交中更新 uniform、可见性、材质、DOM 控件和画布；不得先暴露半套状态。
- 相机、controls target、presentation root 和 primary subject matrix 不属于 effect timeline。切换、暂停和 replay 不得偷偷重置它们。

## 3. 暂停、回放与后台恢复

### 用户暂停

用户暂停必须冻结全部自主运动：

- effect progress、auto-rotate、damping 惯性；
- shader time、pulse、粒子、扫描光、局部光和临时 CSS 动画；
- 未经用户输入的相机、目标点和主体矩阵变化。

暂停后仍允许用户主动拖拽和缩放；交互结束后不得恢复自主运动。按钮事件和 acceptance bridge 必须调用同一个 playback controller，不得维护两套语义。

### Replay

- replay 将 timeline 原子重置到 `progress=0`，保留用户相机和 controls target。
- 第一个已提交画面必须已经是 0 状态；禁止 UI 显示“重播中”而画布仍停留在完成态一帧。
- `prefers-reduced-motion` 下 replay 仍保持完成态和 paused，不制造短暂运动。

### 后台恢复

- 监听 `visibilitychange`。进入 hidden 时记录“隐藏前是否播放”，停止自主更新并保存当前进度。
- 回到 visible 时重置时间基线；只有隐藏前正在播放且用户没有显式暂停时才恢复。
- 恢复首帧不得补算隐藏期间的墙钟时间，也不得出现进度倒退或大步跳跃。

## 4. Shader、透明层与深度稳定性

- 高频表面细节优先使用纹理 mipmap、导数抗锯齿或低频连续噪声。会随相机产生逐像素跳变的 `sin/fract` 颗粒、法线扰动和窄亮带必须降频或过滤。
- 细线宽度、扫描边界和发光尾在两个目标 DPR 下都不得细于稳定可见阈值；用 subject crop 的连续帧差分验证，而不是只看静止截图。
- 透明层默认 `depthTest=true`、`depthWrite=false`，但这不是共面稳定性的充分条件。共面 overlay 必须采用有依据的几何偏移、clip-space depth bias、polygon offset 或独立深度预通道。
- 不得把 `renderOrder` 当作消除 z-fighting 的方案；它只处理绘制顺序。保持相机 near 尽量远、far 尽量紧，提升有效深度精度。
- 多层透明必须明确背面/正面和遮挡顺序；如果顺序依赖视角且无法稳定排序，拆分几何或改用不透明/抖动透明方案。
- halo、emissive、局部光、阴影和裁切的进入/退出使用连续 easing。需要布尔切换时，先让视觉强度衰减到零，再在不可见点关闭资源。
- 在 `progress=1` 附近至少采样 `0.98 / 0.99 / 1`，不得出现无设计依据的全局亮度尖峰、主体覆盖率骤降或轮廓跳变。

## 5. 预热、首帧与画廊切换

- 加载完成不等于首帧稳定。隐藏 loading 前必须完成：资产指纹/结构校验、所选 effect shader variant 预编译、真实尺寸 render、至少两个 settle frame 和 acceptance bridge ready。
- Three.js 支持时使用 `compileAsync()` 预热将被切换到的材质和 shader variant；否则逐模式离屏预渲染并恢复目标状态。
- 模式切换不得在首次点击时同步编译 shader。预热后再允许控件进入可交互状态。
- 集成画廊采用“旧帧保留、新帧候选、原子替换”：新 iframe 未通过子页面 ready、样式 load 和真实首帧门禁前，旧的已验证画面继续可见。
- 交换时同一视口最多一个可见画布；允许短暂同时挂载，但不允许两个可见 WebGL 主体、两个 loading 或空白背景。
- `iframe load`、HTTP 200、DOM ready、固定等待时间和 opacity transition 都不能单独作为新帧 ready 证据。

## 6. 连续帧浏览器验收矩阵

所有项目必须在真实 Chrome/Chromium、`1440×900` 与 `390×844`、DPR 1 执行。默认在内存中完成帧差分并只写结构化统计，不落盘截图；用户明确要求视觉验收时，截图差分只裁主体 canvas/safe rect，排除光标、时间文本和无关 UI。

| 场景 | 操作与采样 | 硬断言 |
| --- | --- | --- |
| 冻结基线 | settle 2 帧后，间隔至少 120ms 取 3 帧 | progress、camera、matrix 不变；主体最大像素差分比不超过项目阈值 |
| 用户暂停 | 通过真实按钮播放后暂停，再取 3 帧 | 与冻结基线同样稳定；auto-rotate、damping、shader time 和 pulse 均停 |
| Replay 原子性 | 修改用户视角后触发 replay，逐 RAF 采 8 帧 | 首个已提交画面已是 0 状态；相机保留；无一帧旧完成态 |
| 连续播放 | 每 100ms 采样直到完成 | progress 单调；无空白帧、主体消失、模式串帧或异常亮度尖峰 |
| 模式切换 | 覆盖所有已选模式对，每次切换前后逐 RAF 采 12 帧 | 目标状态原子；空白帧 0；可见画布最多 1；无首次 shader 编译闪烁 |
| 后台恢复 | 播放中隐藏再恢复；用户暂停后再重复 | 恢复首帧只重置时间基线；无进度跳跃；暂停态不自动恢复 |
| 完成态 | 采 `0.98 / 0.99 / 1` 和完成后 3 帧 | 临时资源清零；无亮度/覆盖率突变；完成后稳定 |
| 资源稳定 | 切换、重播、resize 各 10 次 | loop owner 为 1；`renderer.info` 不持续增长；dispose 后资源和监听清理 |
| 画廊交换 | 桌面和移动端连续切换全部地标 | 新首帧 ready 前旧帧保留；空白、双主体、双 loading 和旧残影均为 0 |

项目应在 browser report 记录差分算法和阈值；阈值必须先由同机同状态冻结基线标定，不能用宽松阈值掩盖肉眼闪烁。

## 7. 报告数据合同

`browser_report` 在原有字段之外必须包含：

```json
{
  "motion_stability": {
    "status": "passed",
    "sample_count": 3,
    "frozen_frame": { "passed": true, "pixel_diff_ratio_max": 0 },
    "ui_pause": { "passed": true, "progress_stable": true, "camera_stable": true, "pixels_stable": true },
    "replay": { "passed": true, "atomic_first_frame": true, "camera_preserved": true },
    "continuous_playback": { "passed": true, "progress_monotonic": true, "unexpected_blank_frames": 0, "unexpected_subject_dropouts": 0 },
    "mode_switch": { "passed": true, "unexpected_blank_frames": 0, "duplicate_visible_canvases": 0 },
    "visibility_resume": { "passed": true, "baseline_reset": true, "unexpected_progress_jump": false },
    "completion": { "passed": true, "temporary_effects_cleared": true, "abrupt_luminance_spike": false },
    "shader_warmup": { "passed": true, "variants_precompiled": true },
    "resource_stability": { "passed": true, "renderer_info_plateau": true }
  },
  "runtime_lifecycle": {
    "animation_loop_owners": 1,
    "visibility_lifecycle": true,
    "dispose_passed": true
  }
}
```

严格交付不接受省略、`not-tested`、只给最终截图或只调用测试冻结接口的替代证据。若浏览器/GPU 无法稳定运行，应报告阻塞，不得把单帧无头截图标为通过。

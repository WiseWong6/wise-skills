# 资产、运行时与视觉验收

## 目录

1. 验收层级与证据封印
2. GLB 门禁
3. 运行时接口
4. 构图与视角
5. 光效状态测试
6. 动效连续性与抗闪烁
7. 双源视觉比较
8. 浏览器与交互
9. 失败恢复、性能和清理
10. 最终报告

## 1. 验收层级与证据封印

- `candidate-ready` 是默认机器交付：GLB、源码、运行时、Khronos、loader、browser 和 HTTP 资产字节属于同一证据轮次。
- `visual-approved` 只在用户明确要求视觉验收，并由用户或明确授权 Reviewer 对当前资产完成七视角复核后成立。
- 默认不主动生成成套截图或执行耗时主观自检；交付绝对路径、服务 URL、七视角操作与失败信号，由用户自检。

机器检查完成后运行 `seal_evidence.py`，再运行 `validate_case.py --strict`。严格校验必须拒绝：非 GLB 文件、伪图片、陈旧报告、报告哈希漂移、loader/browser 资产哈希不一致，以及 HTTP 返回字节未绑定。

完整合同见 [evidence-integrity.md](evidence-integrity.md)。

## 2. GLB 门禁

导出后固定资产 SHA-256，并执行：

1. Khronos 官方 glTF Validator，对 GLB 2.0、schema、accessor、buffer、image、extension 和有限数进行验证。
2. 项目运行时 GLTFLoader/WebGL2 真实加载，确认语义层级、材质、bounds、法线和字节数。
3. 项目特定 landmark 检查，确认尺寸、部件计数、包络、开口、支撑数量等 ModelBrief 约束。

官方资料：

- https://github.com/KhronosGroup/glTF-Validator
- https://www.khronos.org/gltf/
- https://threejs.org/docs/pages/GLTFLoader.html

通过条件：

- Khronos 报告 `issues.numErrors=0`。
- 所有 accessor 和 transform 为有限数，GLB 实际 bounds 与报告一致。
- `mainBuildingRoot` 或项目声明的 primary root 存在，语义部件和材质区域齐全。
- 资产哈希与 DeliveryManifest、ComparisonReport、浏览器报告完全一致。
- GLB 原始字节满足 binary glTF header：magic 为 `glTF`、container version 为 2、声明总长度等于文件长度，首个 JSON chunk 可解析且 `asset.version=2.0`。

Validator 只证明格式和部分数据正确，不证明建筑长得正确。

## 3. 运行时接口

实现稳定的：

```ts
type EffectMode = "color" | "build" | "edge-color";
type CanonicalView =
  | "front"
  | "back"
  | "left"
  | "right"
  | "roof"
  | "ground-contact"
  | "three-quarter";

interface AcceptanceBridge {
  version: 4;
  ready: Promise<void>;
  freezeRafTimeAndDamping(timeMs?: number): Promise<void> | void;
  setPlaybackPaused(paused: boolean): Promise<void> | void;
  replay(): Promise<void> | void;
  setEffectProgress(effect: EffectMode, progress: number): Promise<void> | void;
  setCanonicalView(view: CanonicalView): Promise<void> | void;
  applyDeterministicUserViewDelta(yaw: number, pitch: number, zoom: number): Promise<void> | void;
  capture(label?: string): Promise<AcceptanceSnapshot> | AcceptanceSnapshot;
  captureMotionDiagnostics(): Promise<MotionDiagnostics> | MotionDiagnostics;
  captureSubjectIdMask(): Promise<SubjectMask> | SubjectMask;
  dispose(): void;
}

declare global {
  interface Window {
    __BUILD_WHITE_MODEL_MOTION_ACCEPTANCE__?: AcceptanceBridge;
  }
}
```

`capture()` 至少返回：

- asset SHA-256、effect、progress、phase、paused 和 reducedMotion。
- animation loop owner 数量、RAF timestamp/baseline、visibility state、auto-rotate、damping、shader time 和 pulse。
- camera、projection、controls target、presentation root 和 primary subject matrix。
- 主体 bounds/anchor/safe rect、object-ID mask 元数据。
- 可见光圈、临时 emissive、临时 overlay、clipping/reveal uniform、局部光强度。
- 03 的 feature IDs、可达性、覆盖率、可见线段数、depthTest 和 depthWrite。

模板 `assets/case-template/runtime/acceptance-contract.js` 只提供接口适配器；项目必须实现真实 capture，不得返回静态假数据。

`freezeRafTimeAndDamping()` 只用于建立确定性截图基线，不能代表用户暂停通过。真实按钮和 `setPlaybackPaused()` 必须进入同一个 playback controller；`captureMotionDiagnostics()` 用于证明所有自主运动源都已冻结或恢复。

## 4. 构图与视角

标准视口：

- `desktop-1440x900`，DPR 1。
- `compact-390x844`，DPR 1。

标准视角：

- `front / back / left / right / roof / ground-contact / three-quarter`。

构图规则：

- 用完整完成态主体的 object-ID tight silhouette 做 maximum-uniform-contain。
- object-ID pass 排除 context、ground、shadow、halo、effects 和 dock。
- fit 只能改变相机距离或 presentation root 的统一比例/屏幕平移，不能改 model root。
- 光效切换、重播和 progress 变化不得重新 fit。
- safe rect overflow 必须为 0；紧凑视口中模型和全部控件必须可见。

每个项目冻结自己的目标 anchor 和 safe rect。不要直接复用巴黎铁塔像素 golden；只复用算法和状态合同。

## 5. 光效状态测试

对每个已选模式捕获 `progress=0`、一个有代表性的中段和 `progress=1`。

公共断言：

- 0、mid、1 的 camera、projection、controls target、presentation root 和 primary subject matrix 不漂移。
- 完成态主体 bounds 和 object-ID mask 与无光效完成态一致。
- `progress=1` 的 visible halo、temporary emissive、temporary overlay、clipping/reveal uniform 和 moving local light 全部为 0。
- 点击光效按钮与直接调用 acceptance bridge 得到同一模式和进度语义。
- replay 保留用户修改后的视角，只重启时间线。
- 暂停、replay 和切换必须在单次状态提交中同步 DOM 与 WebGL，不能暴露一帧旧画面。

01 额外断言：

- 中段有且仅有一个语义光圈，包含 core/glow/soft-disc 三层。
- 所有截面检查点的 X/Z 余量为正，光圈不靠可见旋转伪装。
- 扫描后区域恢复真实材质，扫描前区域保持暖白。

02 额外断言：

- 中段只出现已建造部分，visible halo 为 0。
- 边界窄且与合法生长轴一致；完成态不残留裁切。

03 额外断言：

- required feature reachability 为 1，关键 feature 全部可达。
- horizontal band、halo、global rim 和 moving local light 为 0。
- 线条 depthTest=true、depthWrite=false；光尾短，完成态 visible segment count 为 0。

弱动态断言：直接进入完成态、paused=true、turntable=0、pulse=0、临时光效=0。

## 6. 动效连续性与抗闪烁

单帧状态矩阵之外，必须在两个标准 viewport 执行连续帧测试：

- 冻结基线：settle 两帧后间隔至少 120ms 捕获三帧，记录主体 crop 像素差分阈值。
- 真实暂停：通过页面按钮播放后暂停，证明 progress、camera、matrix、auto-rotate、damping、shader time、pulse 和主体像素稳定；不得只调用 `freezeRafTimeAndDamping()`。
- replay：修改用户相机后逐 RAF 采 8 帧，首个已提交帧必须是 0 状态且相机不回 canonical view。
- 连续播放：至少每 100ms 采样至完成，进度单调，空白帧、主体丢失和模式串帧均为 0。
- 模式切换：覆盖所有已选模式对，切换前后逐 RAF 采 12 帧；shader 已预热，DOM 和画布原子一致。
- 后台恢复：覆盖播放中和用户暂停两种 hidden/visible 流程；恢复首帧重置时间基线，不补算隐藏时间。
- 完成态：采样 `0.98 / 0.99 / 1` 及完成后稳定帧，临时光、overlay、裁切、线段和 shader time 均按合同清理，无亮度尖峰。
- 资源循环：切换、重播和 resize 各 10 次，animation loop owner 始终为 1，`renderer.info` 不持续增长。

透明/线框门禁：共面或近共面层必须有明确 depth bias、几何偏移或独立深度策略；`renderOrder` 不能作为消除 z-fighting 的证据。高频程序纹理和法线扰动需要抗锯齿、降频或纹理 mipmap，并通过运动中的 subject crop 差分复核。

`browser_report.motion_stability` 和 `runtime_lifecycle` 的必需字段、画廊原子交换规则及测试表见 [motion-stability.md](motion-stability.md)。

## 7. 双源视觉比较

用户明确要求视觉验收时，对每个标准视角分别完成两个结论。默认 `user-self-check` 不由 Builder 擅自写 `pass`，只给出相同视角的操作、来源锚点与失败信号。

### 真实素材结论

检查身份、比例、轮廓、主负空间、屋顶、立面节奏、背面、落地、结构连续性、材质事实和目标版本。出现差异时直接修改模型或材质，不通过镜头规避。

### 方向图结论

在同 viewport、同机位和同主体阶段下检查构图、视觉层级、暖白/真实材质关系、光效位置、亮度层级和页面色系。方向图与真实资料冲突时修方向图，不改真实结构去迎合生成错误。

比较循环固定为：

`capture → compare → find → revise → recapture`

不接受以下替代：

- 只看单张三分之四截图。
- 只报 RMSE、SSIM、像素相似度或模型面数。
- 只让 validator、lint、build 或无头截图判定视觉通过。
- 用旧资产截图绑定新 GLB 哈希。

## 8. 浏览器与交互

在真实 Chrome/Chromium 检查：

- HTTP 入口、GLB 和模块请求成功，控制台、pageerror 与 WebGL 错误为 0。
- 运行时、报告和实际 HTTP 返回的 GLB 字节必须对应同一个 SHA-256；出现模型指纹不匹配即失败，不得绕过校验。
- browser report 必须把 HTTP 实际响应字节计算为 `http_asset_sha256`；检查文本里写“PASS served SHA”不能替代机器字段。
- 初始 loading、ready、error、retry 状态可见且可恢复。
- loading 固定在当前 3D 视口中心并标记 `data-landmark-loading`；底部播放条固定居中并标记 `data-landmark-playback`，两者符合 `presentation-shell.md` 和目标工作区 `AGENTS.md`。
- 拖拽旋转、滚轮缩放、光效切换、timeline、暂停和重播真实有效。
- 用户视角变化后切换光效和重播不跳回 canonical pose。
- 从桌面 resize 到紧凑视口会重新执行该 viewport 的完整态 fit，不沿用错误比例。
- 字体、控件、焦点样式和触控命中区在两类视口完整。
- loading 验收时加载阶段恰好一个可见实例且中心与 3D 视口中心一致；ready/error 后可见实例为零。
- 集成画廊切换时无旧 iframe/WebGL 残影，且不得生成第二个 loading。
- 新 iframe 未完成子页面 ready、样式加载、shader 预热和真实首帧前，保留旧的已验证画面；`iframe load` 不能单独作为 ready。
- 页面 hidden/visible 后不跳进度，不意外恢复用户暂停；切换模式首次使用时无 shader 编译闪帧。

自动化浏览器通过只构成 `candidate-ready`。GUI/人工视觉结果只有在用户明确要求视觉验收时才进入 `visual-approved`；无头成功不能被改写成人工视觉通过。

## 9. 失败恢复、性能和清理

- 模拟 GLB 404/解析失败，要求可见错误和可操作重试。
- 记录 bytes、load duration、draw calls、triangles、textures 和 programs；数值只作当前机器回归，不宣称网络 SLA。
- 连续执行切换、重播和 resize，确认资源计数不持续增长。
- 在 dispose/pagehide 中停止唯一 animation loop，取消事件、计时器、object URL 和加载请求，释放所有 GPU 资源；visibility 恢复只重置时间基线。
- 开始前检查等效服务；结束后只停止本轮启动的进程。
- 保留结构化报告与 evidence seal。只在用户明确要求截图/视觉验收时保留交付截图；缓存、临时 npm 目录、失败截图和日志记录后清理。

## 10. 最终报告

最终报告按顺序写：

1. 一句话结果和交付边界，明确 `candidate-ready` 或 `visual-approved`。
2. 改了什么：参考、几何、材质、光效、运行时。
3. 如何验证：命令、浏览器入口、视口和人工步骤。
4. 实际结果：GLB 哈希/统计、evidence run ID、validator、浏览器、七视角机器状态和 HTTP 字节哈希。
5. 剩余风险：数据精度、未知隐藏面、近似结构、性能和兼容性。
6. 产物：GLB、源码、方向图、报告、可选视觉验收截图、临时产物清理状态。
7. commit hash 和服务 URL（如有）。没有 commit 或服务时明确说明。

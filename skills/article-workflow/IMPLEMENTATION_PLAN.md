# 横屏改造实施计划

---

## ⚠️ DEPRECATED

**本文档已被 TEST_RESULTS.md（v1.3）替代。**

请以 `/insurance-article-creator/TEST_RESULTS.md` 为唯一验收口径。

---

## 原文档内容（仅供参考）

## 验收时间
2026-01-13

---

## 一、硬要求（必须做到）

### 1.1 run_context.yaml 必须自解释（Self-Describing Run）

**当前状态**：
- `run_context.yaml` 存在 `templates/` 目录
- 包含基本字段：run_id, topic, platforms, status, current_step, decisions, pending_questions, steps
- 缺少 workflow 元数据字段

**需要新增**：
```yaml
workflow:
  name: "insurance-article-creator"
  version: "x.y.z"
  manifest_path: "workflow_manifest.yaml"
  manifest_hash: "<sha256>"
```

### 1.2 新增 steps 列表（顺序即执行顺序）

**当前状态**：
- steps 是一个字典，包含每个步骤的状态和产物
- 结构：
  ```yaml
  steps:
    00_init:
      state: "PENDING"
      artifacts: []
    01_research:
      state: "PENDING"
"      artifacts: []
    ...
  ```

**需要修改**：
- 在每个步骤方法执行后，通过 `update_step_state()` 更新状态
- 状态流转：PENDING -> RUNNING -> DONE/FAILED/WAITING_FOR_USER

### 1.3 新增 gates 列表（或 decisions.xxx.confirmed 机制）

**需求**：
- Gate A: 公众号账号选择
- Gate B: 图片配置确认（横/竖屏 + 张数）
- Gate C: （如需要）

**当前问题**：
- Gate B 当前检查 `orientation` 是否为 None
- 但没有使用 `confirmed` 机制
- 导致即使模板有默认值，也会被跳过

**需要新增**：
- 在 `decisions.image` 下新增 `confirmed: false` 字段
- Gate B 检查逻辑修改为：
  ```python
  if not decisions.image.confirmed:
      # 进入 WAITING_FOR_USER 并提问
  ```

**步骤 ID 与依赖关系**：
| 步骤 ID | depends_on | 说明 |
|---------|-----------|------|
| 00_init | | 初始化 run 目录 |
| 01_research | 00_init | 生成调研内容 |
| 02_draft | 01_research | 生成初稿 |
| 03_polish | 02_draft | 润色（含 RAG 检索）|
| 04_humanize | 03_polish | 去机械化 |
| 05_prompts | 04_humanize | 生成提示词 |
| 06_images | 05_prompts | 生成图片 |
| 07_wx_html | 06_images | HTML 转换 + 合流校验 |
| 08_draftbox | 07_wx_html | 上传草稿箱 |

---

## 二、Gate B（横/竖屏）必须修的点

### 2.1 修复 decision 写入路径错误

**当前代码**（orchestrator.py:69-76）：
```python
def update_decision(self, key: str, value: Any):
    """更新决策"""
    keys = key.split('.')
    target = self.data["decisions"]
    for k in keys[:-1]:
        target = target.setdefault(k, {})
    target[keys[-1]] = value  # ❌ 错误：keys[-1] 应该是 keys[-1]
    self.save()
```

**问题**：
- 当前实现使用了错误的切片 `keys[:-1]`
- 如果 key 是 `image.orientation`，最后迭代时 `keys[-1]` 是空字符串

**需要修改**：
```python
def update_decision(self, key: str, value: Any):
    """更新决策"""
    keys = key.split('.')
    target = self.data["decisions"]
    for k in keys[:-1]:  # 保留
        target = target.setdefault(k, {})
    target[keys[-1]] = value
    self.save()
```

### 2.2 解决"默认横屏"与"强制确认"的冲突

**当前代码**（orchestrator.py:180-214）：
```python
def check_gate_b(self) -> bool:
    """检查 Gate B: 图片配置确认"""
    # 先检查 orientation（新增）
    orientation = self.context.get_decision("image.orientation")
    if orientation is None:
        # 兼容旧 run_context：没有 orientation 字段时强制询问
        question = {...}
        self.context.add_pending_question(question)
        print("\nGate B: 需要确认图片配置（横/竖屏 + 张数）")
        return False  # 返回 False，不继续执行
    # ...
    return True
```

**问题**：
- 只有 `orientation is None` 时才提问
- 如果模板中默认了 `orientation: "landscape"`，不会触发 Gate B
- 导致用户无法确认或修改默认值

**需要修改**：
- 在 `decisions.image` 下新增 `confirmed: false` 字段
- Gate B 检查逻辑修改为：
  ```python
  def check_gate_b(self) -> bool:
      """检查 Gate B: 图片配置确认"""
      # 检查确认状态
      confirmed = self.context.get_decision("image.confirmed", False)
      if not confirmed:
          # 进入 WAITING_FOR_USER 并提问
          # ...
          return False
      return True
  ```
- 用户确认后设置 `decisions.image.confirmed = true`

### 2.3 输入校验逻辑必须"缺一项就继续问"

**当前代码**（orchestrator.py:255-263）：
```python
# 先检查是否包含有效的 orientation 和 count
has_orientation = any(keyword in answer for keyword in ["横屏", "竖屏", "landscape", "portrait"])
has_count = re.search(r'\d+\s*[张张]', answer)

# 如果用户没有明确指定横/竖屏和数量，继续等待
if not has_orientation and not has_count:
    print("请明确选择横屏或竖屏，并指定张数（如：横屏，4张）")
    # 不更新任何决策，保持 WAITING_FOR_USER
    return False
```

**问题**：
- 当前逻辑使用 `and` 连接：`not has_orientation and not has_count`
- 这意味着用户必须**同时**提供 orientation 和 count 才能继续
- 但用例要求用户可以单独输入"横屏"或"4张"

**需要修改**：
- 改为"两段式"校验：
  ```python
  # 第一段：检查 orientation
  has_orientation = any(keyword in answer for keyword in ["横屏", "竖屏", "landscape", "portrait"])
  if not has_orientation:
      print("请明确选择横屏或竖屏（如：横屏）")
      return False

  # 第二段：检查 count
  has_count = re.search(r'\d+\s*[张张]', answer)
  if not has_count:
      print("请指定张数（如：4张）")
      return False

  # 两段都通过后才继续
  ```

### 2.4 count 解析要支持"横屏，4（无张）"，同时避免误把 16:9 的数字当 count

**当前代码**（orchestrator.py:281）：
```python
count_match = re.search(r'(\d+)\s*[张张]', answer)
if count_match:
    count = int(count_match.group(1))
else:
    # 默认 4 张
    count = 4
```

**问题**：
- 如果用户输入"横屏 16:9"，`16:9` 可能被误识别为 count
- 需要先过滤掉比例 token 再匹配数字

**需要修改**：
```python
# 先过滤掉比例相关的 token（16:9, 16x9, 3:4, 3x4 等）
# 然后再匹配数字
import re

# 预处理：移除常见比例格式
answer_cleaned = answer.replace("16:9", "").replace("16x9", "").replace("3:4", "").replace("3x4", "")

# 然后匹配
count_match = re.search(r'(\d+)\s*[张张]', answer_cleaned)
if count_match:
    count = int(count_match.group(1))
else:
    # 默认 4 张
    count = 4
```

---

## 三、防回归用例（必须新增/修正）

### 3.1 Gate B：只输入"横屏" -> 必须继续 WAITING 并追问张数

**期望行为**：
- 用户输入："横屏"
- 系统应该继续 WAITING_FOR_USER
- 输出提示："请指定张数（如：横屏，4张）"

**测试用例**：
```python
# 当前解析逻辑
has_orientation = any(keyword in "横屏" for keyword in ["横屏", "竖屏", "landscape", "portrait"])
has_count = re.search(r'\d+\s*[张张]', "横屏")

# 用例：has_orientation=True, has_count=False
# 预期：has_orientation=True, has_count=False，但由于 and 逻辑，会继续等待
# 正确：应该继续等待并提示
if not has_orientation and not has_count:
    print("请明确选择横屏或竖屏，并指定张数（如：横屏，4张）")
    return False
```

### 3.2 Gate B：只输入"4张" -> 必须继续 WAITING 并追问横/竖屏

**期望行为**：
- 用户输入："4张"
- 系统应该继续 WAITING_FOR_USER
- 输出提示："请明确选择横屏或竖屏（如：横屏，4张）"

**测试用例**：
```python
# 输入："4张"
has_orientation = any(keyword in "4张" for keyword in ["横屏", "竖屏", "landscape", "portrait"])  # False
has_count = re.search(r'\d+\s*[张张]', "4张")  # True (匹配到 4)

# 当前逻辑：has_orientation=False, has_count=True
# 由于 and 条件（False and True），会继续执行（错误！）
# 正确：应该继续等待并提示
if not has_orientation and not has_count:
    print("请明确选择横屏或竖屏，并指定张数（如：横屏，4张）")
    return False
```

### 3.3 Gate B：输入"横屏，4" -> 必须 PASS（orientation=landscape, count=4）

**测试用例**：
```python
# 输入："横屏，4"
# 当前解析逻辑
has_orientation = any(keyword in "横屏，4" for keyword in ["横屏", "竖屏", "landscape", "portrait"])  # True
has_count = re.search(r'\d+\s*[张张]', "横屏，4")  # True

# 当前逻辑：has_orientation=True, has_count=True
# 由于 and 条件（True and True），会继续执行（正确！）
# 但由于 count_match 的正则，可能会把 "4张" 匹配为 4，也可能把 "横屏，4" 中的 4 匹配
# 建议：先过滤比例，再匹配数字（见 2.4）
```

### 3.4 Gate B：输入"竖屏，5张，封面16:9，正文3:4" -> PASS 且 poster_ratio 派生正确

**期望行为**：
- orientation = "portrait"
- count = 5
- poster_ratio = "3:4" (派生)
- cover_ratio = "16:9"

**测试用例**：
```python
# 输入："竖屏，5张，封面16:9，正文3:4"
# 当前解析逻辑应能正确处理
# 已在 TEST_RESULTS.md 中验证通过
```

### 3.5 Gate B：输入"横屏，4张，正文21:9" -> PASS（覆盖默认）

**期望行为**：
- orientation = "landscape"
- count = 4
- poster_ratio = "21:9" (用户指定，覆盖默认)
- cover_ratio = "16:9"

### 3.6 新 run：即便模板默认 orientation=landscape，也必须触发 Gate B

**需求**：
- 在 `decisions.image` 下新增 `confirmed: false`
- 首次运行时，先检查 `confirmed` 状态
- 只有用户确认后设置 `confirmed = true`，才继续执行

**需要修改**：
- run_context.template.yaml 中的 orientation 默认值保持不变
- 但需要新增 `decisions.image.confirmed: false` 字段
- `check_gate_b` 修改为检查 `confirmed` 状态

---

## 四、发布链路

### 4.1 确保每一步都会写自己的 handoff.yaml

**当前状态**：
- 每个步骤调用 `write_handoff()` 生成 handoff.yaml
- `write_handoff()` 接受：platform, step_id, inputs, outputs, summary, next_instructions

**需要验证**：
- 检查每个步骤是否正确调用了 `write_handoff()`
- handoff 文件应包含完整的 inputs 和 outputs 列表
- handoff 文件名格式：`{step_num}_handoff.yaml`（step_num 是两位数字）

### 4.2 贯穿到：05_prompts -> 06_images -> 07_wx_html -> 08_draftbox

**当前链路（已验证通过）**：
- step_prompts 写入：wechat/05_prompts.md, 05_handoff.yaml
- step_images 读取：05_handoff.yaml，生成：wechat/06_images/*
- step_wx_html 读取：05_handoff.yaml 和 06_images，生成：wechat/07_article.html, 07_handoff.yaml
- step_draftbox 读取：07_handoff.yaml，上传草稿箱

**需要验证**：
- 每个 handoff 的 inputs 应引用前一步的 outputs
- 每个 handoff 的 next_instructions 应指向下一步

---

## 五、实施步骤建议

由于修改涉及范围较广，建议按以下顺序实施：

### 阶段 1：基础架构（必须优先）
1. 修改 `run_context.template.yaml`，新增 workflow 字段和 gates 机制
2. 修改 `run_context.template.yaml`，新增 `decisions.image.confirmed: false`
3. 测试模板复制机制是否正常工作

### 阶段 2：修复 Gate B
4. 修复 `orchestrator.py` 中的 `update_decision()` 方法（keys[-1] 错误）
5. 修改 `orchestrator.py` 中的 `check_gate_b()` 方法，添加 `confirmed` 检查
6. 修改 `orchestrator.py` 中的 `process_pending_questions()` 方法，改为两段式校验
7. 修改 `orchestrator.py` 中的 `process_pending_questions()` 方法，添加比例 token 过滤（count 解析）

### 阶段 3：测试验证
8. 更新 `test_tc05_orientation.py`，新增更多边界用例
9. 更新 `test_tc06_wx_html_ratio.py`（如需要）
10. 运行完整测试，验证端到端流程

### 阶段 4：文档更新
11. 更新 `TEST_RESULTS.md`，记录所有修改

### 阶段 5：发布验证
12. 确认 `--status` CLI 参数实现（如果需要）
13. 验证完整流程的可断续性

---

## 六、验收标准

完成以下所有修改后，应满足：

### 架构层面
- ✅ run_context.yaml 自解释（包含 workflow 字段）
- ✅ steps 字段结构正确
- ✅ gates 机制（decisions.xxx.confirmed）正常工作
- ✅ 每步正确写 handoff.yaml
- ✅ 步骤依赖关系正确

### Gate B 兼容性
- ✅ 新 run 触发 Gate B（confirmed=false）
- ✅ 只输入"横屏" -> 继续等待并追问张数
- ✅ 只输入"4张" -> 继续等待并追问横/竖屏
- ✅ 输入"横屏，4" -> PASS（orientation=landscape, count=4）
- ✅ 输入比例变体能正确解析
- ✅ poster_ratio 正确派生

### 防回归能力
- ✅ 所有测试用例通过
- ✅ 端到端流程可复现

### 文档完整性
- ✅ IMPLEMENTATION_PLAN.md 完整
- ✅ TEST_RESULTS.md 更新
- ✅ 代码注释清晰（如有必要）

---

## 附录：关键代码位置参考

| 文件 | 代码位置 | 功能 |
|------|---------|------|
| run_context.template.yaml | /templates/ | 模板定义 |
| orchestrator.py | ~第 69-76 行 | update_decision() 方法 |
| orchestrator.py | ~第 180-214 行 | check_gate_b() 方法 |
| orchestrator.py | ~第 216-307 行 | process_pending_questions() 方法 - image_config 处理 |
| orchestrator.py | ~第 1285-1355 行 | step_wx_html() 方法 - 合流校验 |
| orchestrator.py | ~第 1445-1538 行 | step_draftbox() 方法 - 草稿箱上传 |

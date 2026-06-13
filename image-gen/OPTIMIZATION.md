# Article Workflow 图片上传问题诊断与优化

## 问题回顾

### 现象
在执行 article-workflow 时，步骤 11（wechat-draftbox）上传草稿后，发现正文中的图片没有正确显示。

### 根本原因

**流程断裂：图片生成与内容插入脱节**

```
步骤 07: article-humanizer → 07_final_final.md (纯文本，无图片)
                          ↓
步骤 08: image-prompter    → 生成提示词 (但不知道要插入哪里)
                          ↓
步骤 09: image-gen         → 生成图片到 09_images/ (与 Markdown 脱节)
                          ↓
步骤 10: md-to-wxhtml      → 转换 HTML (Markdown 中无图片引用！)
                          ↓
步骤 11: wechat-draftbox   → 上传草稿 (扫描 HTML，找不到本地图片)
```

### 技术细节

**草稿箱脚本的工作原理：**
```python
# wechat-draftbox 脚本扫描 HTML 中的图片
def replace_local_images(access_token, content_html, html_dir):
    # 查找 <img src="..."> 标签
    # 如果 src 是本地路径 → 上传到微信 → 替换为 CDN URL
    # 如果 src 是 http:// → 跳过（外部链接）
```

**问题：** `07_final_final.md` 中完全没有 `![](path.jpg)` 格式的图片引用，所以 HTML 中没有 `<img>` 标签，草稿箱脚本无图可传。

---

## 优化方案

### 修改内容

为 `image-gen` 技能添加 `--insert-into` 参数，实现图片自动插入到 Markdown。

### 新增功能

#### 1. 新参数
```bash
--insert-into <path>  # 指定 Markdown 文件路径
```

#### 2. 插入策略
```
第 1 张图片 → 主标题 (# 标题) 后
第 2+ 张图片 → 各章节标题 (## 章节名) 后
```

#### 3. 相对路径处理
```python
# 自动计算图片相对路径
img_dir = Path(images_dir).relative_to(md_path.parent)
# 生成: ![封面](09_images/image_01.jpg)
```

### 使用方式

```bash
# 生成图片并自动插入到 Markdown
python scripts/generate_image.py \
  --prompt-file "wechat/08_prompts.md" \
  --out-dir "wechat/09_images/" \
  --insert-into "wechat/07_final_final.md"
```

### 修改文件

| 文件 | 修改内容 |
|------|---------|
| `image-gen/scripts/generate_image.py` | 添加 `--insert-into` 参数 + `insert_images_to_markdown()` 函数 |
| `image-gen/skill.md` | 更新文档，说明新参数和使用方式 |

---

## 设计思考

### 为什么在 image-gen 而非其他步骤？

| 方案 | 优点 | 缺点 |
|------|------|------|
| **在 image-gen 中插入** | ✅ 图片生成后立即处理，职责明确 | 需要 Markdown 文件路径 |
| 在 article-humanizer 中插入 | 知道图片提示词 | 需要等待图片生成完成 |
| 在 md-to-wxhtml 中插入 | 转换时统一处理 | 不符合"只做语法转换"的设计原则 |
| 新建单独步骤 | 职责清晰 | 增加步骤复杂度 |

### 职责划分原则

```
article-humanizer  → 文本去机械化 (不管图片)
image-gen          → 生成图片 + 插入 Markdown (新增职责)
md-to-wxhtml       → 语法转换 (不管图片来源)
wechat-draftbox    → 上传 + URL 替换 (只处理已有图片)
```

---

## 后续建议

### 1. orchestrator 层面

需要在 article-workflow orchestrator 中传递必要参数：

```python
# 步骤 09: image-gen 调用时
{
    "input": "wechat/08_prompts.md",
    "insert_into": "wechat/07_final_final.md",  # 新增
    "output_dir": "wechat/09_images/"
}
```

### 2. 其他技能可借鉴的优化

**article-humanizer**：可以添加 `--preserve-images` 参数，保留已有图片引用。

**md-to-wxhtml**：当前设计合理，保持"纯语法转换"的定位。

---

## 总结

### 问题本质
技能之间的协作缺乏"胶水"层——图片生成和内容插入是两个独立流程，没有自动连接。

### 解决方案
在 `image-gen` 中添加图片插入功能，使其成为"生成+插入"的完整步骤。

### 收益
- ✅ 用户无需手动修改 Markdown
- ✅ 图片生成和内容插入原子化完成
- ✅ 减少 workflow 调用复杂度
- ✅ 更符合"自动化内容生产"的设计目标

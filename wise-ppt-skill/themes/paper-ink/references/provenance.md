# 纸墨主题参考源与继承边界

纸墨主题的第一份成品参考来自本机：

`file:///Users/wisewong/Documents/Developer/infra-lesson/trace/video/index.html`

经真实浏览器核验，该参考包含 20 个正式镜头、5 个 act，并有 `lab`、`bak` 两个变体；正式镜头既有 breathing 叙事页，也有连续的 dense 架构、规格和 UI 页面。

它只是可追溯的 reference exemplar，不是 runtime、Core、schema 或打包依赖。本 skill 不复制源文件；换机器或源目录不可用时，主题仍应完整工作。

## 继承

- 把证据、界面、文献和概念做成可审视的“标本”。
- 保留尺寸线、构造线、图题、引线和刻度等测量标注。
- 以单色纸墨为默认；功能性强调色只落到唯一主角。
- 使用精密细线、出版物字体和克制的纸面质感。
- 用 breathing、balanced、dense 的切换形成叙事节奏；高密度不是例外或缺陷。

## 不继承

- 不继承固定 20 页、固定 5 acts 或固定的封面—Context—内容—Outro 页序。
- 不继承所有页面必须中心化；对齐方式由 layout primitives 与信息关系决定。
- 不继承“一页一物”作为字面限制；一页只有一个主要视觉角色，但可以组合多个支持组件。
- 不继承视频时间码、分镜时长、旁白字段或视频播放器结构。
- 不把参考内容、业务数据或页面坐标当成新的用户内容模板。

当参考源与当前 `layout-manifest.json` 冲突时，以 manifest 的机器可读契约和当前 theme tokens 为准；参考源只用于解释视觉血统。

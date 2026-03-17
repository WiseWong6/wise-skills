def step_wx_html(self):
    """生成微信 HTML - 自动插入 CDN 图片后转换"""
    platform = "wechat"
    step_id = "11_wx_html"

    print("生成微信 HTML（自动插入图片 + 转换）...")
    self.log(step_id, "执行 HTML 转换（使用 image_mapping 自动插入 CDN 图片）")

    # 检查前置文件
    md_file = self.run_dir / platform / "07_final_final.md"
    image_mapping_file = self.run_dir / platform / "14_image_mapping.json"

    if not md_file.exists():
        raise FileNotFoundError(f"前置文件不存在: {md_file}")

    # 调用 md-to-wxhtml 转换（传递 image_mapping 让脚本自动插入图片）
    script_path = Path.home() / ".claude" / "skills" / "md-to-wxhtml" / "scripts" / "convert_md_to_wx_html.py"
    html_file = self.run_dir / platform / "11_article.html"

    # 构建命令
    cmd = [sys.executable, str(script_path), str(md_file), "-o", str(html_file)]

    # 如果存在 image_mapping，传递给脚本
    if image_mapping_file.exists():
        cmd.extend(["--image-mapping", str(image_mapping_file)])
        cmd.append("--auto-insert-images")  # 启用自动插入
        self.log(step_id, "使用 image_mapping 自动插入 CDN 图片")
    else:
        self.log(step_id, "未找到 image_mapping，仅转换 Markdown")

    if script_path.exists():
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=self.run_dir)

            if result.returncode != 0:
                self.log(step_id, f"HTML 转换失败: {result.stderr}")
                print(f"HTML 转换失败: {result.stderr}")
                raise RuntimeError(result.stderr)
            else:
                self.log(step_id, "HTML 转换成功")

        except subprocess.TimeoutExpired:
            self.log(step_id, "HTML 转换超时")
            raise
    else:
        # 简化 HTML（后备方案）
        md_content = md_file.read_text(encoding="utf-8")
        html_content = f"""<section style="margin: 20px;">
<p style="margin-left:8px;margin-right:8px;">
<span style="font-size:15px;color:#333;font-family:PingFangSC-Regular;">
{md_content.replace(chr(10), '<br/>')}
</span>
</p>
</section>"""
        html_file.write_text(html_content, encoding="utf-8")
        self.log(step_id, "生成简化 HTML（脚本不可用）")

    # 生成 handoff
    inputs_list = [f"{platform}/07_final_final.md"]
    if image_mapping_file.exists():
        inputs_list.append(f"{platform}/14_image_mapping.json")

    handoff_path = self.write_handoff(
        platform=platform,
        step_id=step_id,
        inputs=inputs_list,
        outputs=[f"{platform}/11_article.html", f"{platform}/11_handoff.yaml"],
        summary=f"将 Markdown 转换为微信 HTML（自动插入 CDN 图片）",
        next_instructions=[
            f"下一步：调用 /wechat-draftbox 上传草稿",
            f"输入：{platform}/11_article.html",
        ]
    )

    print(f"已生成: {html_file.name}")
    print(f"已生成: {handoff_path}")
    return {"artifacts": [f"{platform}/11_article.html", handoff_path]}

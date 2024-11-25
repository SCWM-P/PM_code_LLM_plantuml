import gradio as gr
import io
import sys
from PIL import Image
import pandas as pd
import tempfile
import os
from contextlib import contextmanager
import queue
import threading
import time
from pathlib import Path
import doubleNumberingNetwork as dNN

# 创建一个临时目录来存储图片
if os.path.exists("__temp__"):
    pass
else:
    os.mkdir("__temp__")
# 创建一个队列来存储终端输出
terminal_queue = queue.Queue()


# 创建一个上下文管理器来捕获标准输出和错误
@contextmanager
def capture_output():
    class OutputCapture:
        def write(self, text):
            if text.strip():  # 只有非空内容才加入队列
                terminal_queue.put(text)

        def flush(self):
            pass

    stdout_capture = OutputCapture()
    stderr_capture = OutputCapture()

    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = stdout_capture, stderr_capture

    try:
        yield
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr


def process_image(image):
    """处理上传的图片并返回所有需要的输出"""
    def _load_svg(img_path):
        with open(img_path, 'r', encoding='utf-8') as f:
            return f.read()

    # 将图片保存到临时文件
    output = "svg"
    image_path = "__temp__/upload_image.jpg"
    yaml_path = Path("__temp__/output.yaml")
    txt_path = Path(yaml_path).with_suffix(".txt")
    output_path = Path(yaml_path).parents[0] / f"PERT.{output}"
    # 另存图片到__temp__目录用于处理
    image.save(image_path)
    with capture_output():
        # 1. 使用大模型上传文件和图片提取信息
        response = dNN.upload_and_get_answer(image_path)
        # 2. 提取为YAML格式文件
        yaml_content = dNN.get_yaml(response, yaml_path)
        # 3. 提取Markdown表格
        markdown_table = dNN.get_md_chart(response)
        # 4. 输出PlantUML
        plantuml_text = dNN.convert_yaml2uml(yaml_path, txt_path)
        # 5. 保存PlantUML为PERT图
        dNN.convert_uml2pert(txt_path, output=output)
        # 6. 计算关键路径
        dNN.calc_results(txt_path)
        # 7. 捕捉终端信息
        terminal_content = ""
        while not terminal_queue.empty():
            terminal_content += terminal_queue.get() + "\n"
        print("All processing completed successfully!")
        return (
            response, markdown_table,
            plantuml_text, _load_svg(output_path),
            terminal_content
        )


# 创建Gradio界面
with gr.Blocks(theme=gr.themes.Base()) as demo:
    gr.Markdown("# Image to Table/UML Converter")

    with gr.Row():
        with gr.Column(scale=1):
            # 左侧列
            image_input = gr.Image(label="Upload Image", type="pil")
            response_content = gr.Textbox(
                label="AI Response (Markdown)",
                lines=5,
                placeholder="Extracted table in Markdown format..."
            )

        with gr.Column(scale=1):
            # 右侧列
            table_output = gr.Markdown(
                label="Rendered Table",
                value="Table will appear here..."
            )
            plantuml_output = gr.Textbox(
                label="PlantUML Code",
                lines=5,
                placeholder="Generated PlantUML code..."
            )
            network_output = gr.Image(
                label="Network Diagram",
                # tool="zoom"  # 启用缩放功能
            )

    # 可折叠的终端输出
    with gr.Accordion("Terminal Output", open=False):
        terminal_output = gr.Textbox(
            label="Terminal",
            lines=8,
            max_lines=20,  # 允许拖动调整高度
            placeholder="Process output will appear here...",
            container=False,
            show_copy_button=True
        )

    # 处理函数
    image_input.change(
        fn=process_image,
        inputs=[image_input],
        outputs=[
            response_content,
            table_output,
            plantuml_output,
            network_output,
            terminal_output
        ]
    )

# 启动应用
if __name__ == "__main__":
    demo.launch(share=True)
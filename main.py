import gradio as gr
import sys
from PIL import Image
import os
from contextlib import contextmanager
import queue
from pathlib import Path
import doubleNumberingNetwork as dNN

# 创建一个临时目录来存储图片
if not os.path.exists("__temp__"):
    os.mkdir("__temp__")
# 创建一个队列来存储终端输出
terminal_queue = queue.Queue()
# 将图片保存到临时文件
output_format = "svg"
image_path = "__temp__/upload_image.jpg"
yaml_path = Path("__temp__/output.yaml")
txt_path = Path(yaml_path).with_suffix(".txt")
output_path = Path(yaml_path).parents[0] / f"PERT.{output_format}"
response = ""
markdown_table = ""
plantuml_text = ""
img_content = None
terminal_content = ""


# 创建一个上下文管理器来捕获标准输出和错误
@contextmanager
def capture_output():
    class OutputCapture:
        def write(self, text):
            if text.strip():
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
    global response, markdown_table, plantuml_text, img_content, terminal_content
    def _load_svg(img_path):
        with open(img_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _load_image(img_path):
        return Image.open(img_path)
    if image is None:
        return response, markdown_table, plantuml_text, img_content, terminal_content
    else:
        # 另存图片到__temp__目录用于处理
        image.save(image_path)
        # 初始化输出变量
        response = ""
        markdown_table = ""
        plantuml_text = ""
        img_content = None
        terminal_content = ""
        # 使用队列记录终端输出
        terminal_queue.queue.clear()
        # 开始处理，并逐步yield输出
        yield response, markdown_table, plantuml_text, img_content, terminal_content
        # 1. 使用大模型上传文件和图片提取信息
        response_generator = dNN.upload_and_get_answer(image_path)
        for partial_response in response_generator:
            response = partial_response
            while not terminal_queue.empty():
                terminal_content += terminal_queue.get() + "\n"
            # 更新AI回复部分
            yield response, markdown_table, plantuml_text, img_content, terminal_content

        with capture_output():
            # 2. 提取为YAML格式文件
            yaml_content = dNN.get_yaml(response, yaml_path)
        while not terminal_queue.empty():
            terminal_content += terminal_queue.get() + "\n"
        yield response, markdown_table, plantuml_text, img_content, terminal_content

        with capture_output():
            # 3. 提取Markdown表格
            markdown_table = dNN.get_md_chart(response)
        while not terminal_queue.empty():
            terminal_content += terminal_queue.get() + "\n"
        yield response, markdown_table, plantuml_text, img_content, terminal_content

        with capture_output():
            # 4. 输出PlantUML
            plantuml_text = dNN.convert_yaml2uml(yaml_path, txt_path)
        while not terminal_queue.empty():
            terminal_content += terminal_queue.get() + "\n"
        yield response, markdown_table, plantuml_text, img_content, terminal_content

        with capture_output():
            # 5. 保存PlantUML为PERT图
            dNN.convert_uml2pert(txt_path, output=output_format)
        while not terminal_queue.empty():
            terminal_content += terminal_queue.get() + "\n"
        yield response, markdown_table, plantuml_text, img_content, terminal_content

        with capture_output():
            # 6. 计算关键路径
            dNN.calc_results(txt_path)
        while not terminal_queue.empty():
            terminal_content += terminal_queue.get() + "\n"
        yield response, markdown_table, plantuml_text, img_content, terminal_content

        # 7. 读取生成的PERT图
        if output_format == "svg":
            img_content = _load_svg(output_path)
        else:
            img_content = _load_image(output_path)
        # 8. 最终的终端信息
        print("All processing completed successfully!")
        while not terminal_queue.empty():
            terminal_content += terminal_queue.get() + "\n"
        yield response, markdown_table, plantuml_text, img_content, terminal_content


# 创建Gradio界面
with gr.Blocks(
        css=
        """
    #terminal-output {
        overflow: auto;
    }
    #AI-response {
        overflow: auto;
    }
    .center-text {
        text-align: center;
    }
    h1, h2, h3, h4, h5, h6 {
        text-align: center;
    }
    p {
        text-align: left;
    }
    """
) as demo:
    gr.Markdown("# **📊 Image to Table & UML Converter**")
    gr.Markdown(
        "### 🙌这是一个通过大模型视觉能力将图片转换为表格和UML图表的demo🙌"
    )
    gr.Markdown(
        "### 小组成员：彭博，卞政，冯泺宇，陈俊豪"
    )


    with gr.Row():
        with gr.Column(scale=1):
            # 左侧列
            image_input = gr.Image(
                label="Upload Image",
                type="pil", interactive=True,
                show_label=True,
            )
            with gr.Accordion("Markdown Table Rendered Output", open=True):
                table_output = gr.Markdown(
                    label="Rendered Table",
                    value="Table will appear here...",
                    container=True, show_label=True,
                    height=300, max_height=500
                )
            plantuml_output = gr.Textbox(
                label="PlantUML Code",
                lines=10,
                placeholder="Generating PlantUML code..."
            )

        with gr.Column(scale=1):
            # 右侧列
            with gr.Accordion("Kimi Response", open=True):
                response_content = gr.Markdown(
                    label="AI Response (Markdown)",
                    container=True, show_label=True,
                    height=500, max_height=800,
                    value="AI Response will appear here...",
                    elem_id="AI-response"
                )
            with gr.Accordion("Terminal Output", open=True):
                terminal_output = gr.Textbox(
                            lines=10, max_lines=15,
                            interactive=False,
                            container=True, show_label=False,
                            elem_id="terminal-output"  # 为自定义样式指定ID
                        )

    with gr.Row():
        img_output = gr.HTML(
            label="Network Diagram",
        ) if output_format == "svg" else gr.Image(
            label="Network Diagram"
        )

    # 处理函数
    image_input.change(
        fn=process_image,
        inputs=[image_input],
        outputs=[
            response_content,
            table_output,
            plantuml_output,
            img_output,
            terminal_output
        ],
        queue=True,
    )

# 启动应用
if __name__ == "__main__":
    # 启动应用
    demo.launch(share=True)
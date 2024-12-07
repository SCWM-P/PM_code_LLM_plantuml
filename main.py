import gradio as gr
import sys
from PIL import Image
import os
from contextlib import contextmanager
import queue
from pathlib import Path
import tools as tl

# 创建一个临时目录来存储图片
if not os.path.exists("__temp__"):
    os.mkdir("__temp__")
# 创建一个队列来存储终端输出
terminal_queue = queue.Queue()
# 将图片保存到临时文件
output_format = "svg"
image_path = "__temp__/upload_image.jpg"
yaml_path = Path("__temp__/output.yaml")
puml_path_sNN = Path(yaml_path).parents[0] / f"PUML_text_sNN.puml"
puml_path_dNN = Path(yaml_path).parents[0] / f"PUML_text_dNN.puml"
output_path_sNN = Path(yaml_path).parents[0] / f"PERT_sNN.{output_format}"
output_path_dNN = Path(yaml_path).parents[0] / f"PERT_dNN.{output_format}"
response = ""
markdown_table = ""
plantuml_text_sNN = ""
plantuml_text_dNN = ""
img_content_sNN = None
img_output_dNN = None
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
    global response, markdown_table, plantuml_text_sNN, plantuml_text_dNN, img_content_sNN, img_output_dNN, terminal_content
    def _load_svg(img_path):
        with open(img_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _load_image(img_path):
        return Image.open(img_path)
    if image is None:
        return response, markdown_table, plantuml_text_sNN+"\n"+plantuml_text_dNN, img_content_sNN, img_output_dNN, terminal_content
    else:
        # 另存图片到__temp__目录用于处理
        image.save(image_path)
        # 初始化输出变量
        response = ""
        markdown_table = ""
        plantuml_text = ""
        img_content_sNN = None
        img_output_dNN = None
        terminal_content = ""
        # 使用队列记录终端输出
        terminal_queue.queue.clear()
        # 开始处理，并逐步yield输出
        yield response, markdown_table, plantuml_text_sNN+"\n"+plantuml_text_dNN, img_content_sNN, img_output_dNN, terminal_content
        # 1. 使用大模型上传文件和图片提取信息
        response_generator = tl.upload_and_get_answer(image_path)
        yield response, markdown_table, plantuml_text_sNN+"\n"+plantuml_text_dNN, img_content_sNN, img_output_dNN, terminal_content
        for partial_response in response_generator:
            response = partial_response
            while not terminal_queue.empty():
                terminal_content += terminal_queue.get() + "\n"
            # 更新AI回复部分
            yield response, markdown_table, plantuml_text_sNN+"\n"+plantuml_text_dNN, img_content_sNN, img_output_dNN, terminal_content

        with capture_output():
            # 2. 提取为YAML格式文件
            yaml_content = tl.get_yaml(response, yaml_path)
        while not terminal_queue.empty():
            terminal_content += terminal_queue.get() + "\n"
        yield response, markdown_table, plantuml_text_sNN+"\n"+plantuml_text_dNN, img_content_sNN, img_output_dNN, terminal_content

        with capture_output():
            # 3. 提取Markdown表格
            markdown_table = tl.get_md_chart(response)
        while not terminal_queue.empty():
            terminal_content += terminal_queue.get() + "\n"
        yield response, markdown_table, plantuml_text_sNN+"\n"+plantuml_text_dNN, img_content_sNN, img_output_dNN, terminal_content

        with capture_output():
            # 4. 输出PlantUML
            plantuml_text_dNN = tl.convert_yaml2uml(yaml_path, puml_path_dNN, network="double", quiet=False)
            plantuml_text_sNN = tl.convert_yaml2uml(yaml_path, puml_path_sNN, network="single", quiet=True)
        while not terminal_queue.empty():
            terminal_content += terminal_queue.get() + "\n"
        yield response, markdown_table, plantuml_text_sNN+"\n"+plantuml_text_dNN, img_content_sNN, img_output_dNN, terminal_content

        with capture_output():
            # 5. 保存PlantUML为PERT图
            tl.convert_uml2pert(puml_path_sNN, output_path_sNN, output=output_format)
            tl.convert_uml2pert(puml_path_dNN, output_path_dNN, output=output_format)
        while not terminal_queue.empty():
            terminal_content += terminal_queue.get() + "\n"
        yield response, markdown_table, plantuml_text_sNN+"\n"+plantuml_text_dNN, img_content_sNN, img_output_dNN, terminal_content

        # 6. 读取生成的PERT图
        if output_format == "svg":
            img_content_sNN = _load_svg(output_path_sNN)
            img_output_dNN = _load_svg(output_path_dNN)
        else:
            img_content_sNN = _load_image(output_path_sNN)
            img_output_dNN = _load_image(output_path_dNN)
        # 7. 最终的终端信息
        print("All processing completed successfully!")
        while not terminal_queue.empty():
            terminal_content += terminal_queue.get() + "\n"
        yield response, markdown_table, plantuml_text_sNN+"\n"+plantuml_text_dNN, img_content_sNN, img_output_dNN, terminal_content


def load_example_image(example_path):
    if example_path and os.path.exists(example_path):
        return Image.open(example_path)
    return None


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
    .gr-row {
        align-items: stretch !important;  /* 强制底对齐 */
    }
    .result-images-container {
        display: flex;
        flex-direction: column;
        justify-content: center; /* 居中容器中的子元素 */
        align-items: center;     /* 子元素水平居中 */
        margin-top: 20px;
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

    with gr.Row(equal_height=True):
        with gr.Column(scale=1):
            # 左侧列
            image_input = gr.Image(
                label="Upload Image",
                type="pil", interactive=True,
                show_label=True,
            )
            # 示例图片选择栏
            example_file_paths = ["tests/图片_原始.png", "tests/图片_Excel.png", "tests/网图.png"]
            example_files_dropdown = gr.Dropdown(
                choices=example_file_paths,
                label="Select Example File",
                value=None,
                interactive=True
            )
            example_files_dropdown.change(
                load_example_image,
                inputs=[example_files_dropdown],
                outputs=[image_input]
            )
            # markdown表格输出
            with gr.Accordion("Markdown Table Rendered Output", open=True):
                table_output = gr.Markdown(
                    label="Rendered Table",
                    value="Table will appear here...",
                    container=True, show_label=True,
                )
            # PlantUML输出
            plantuml_output = gr.Textbox(
                label="PlantUML Code",
                placeholder="Generating PlantUML code..."
            )

        with gr.Column(scale=1):
            # 右侧列
            with gr.Accordion("Kimi Response", open=True):
                response_content = gr.Markdown(
                    label="AI Response (Markdown)",
                    container=True, show_label=True,
                    max_height=500,
                    value="AI Response will appear here...",
                    elem_id="AI-response"
                )
            with gr.Accordion("Terminal Output", open=True):
                terminal_output = gr.Textbox(
                            interactive=False,
                            container=True, show_label=False,
                            elem_id="terminal-output"
                        )

    with gr.Row(elem_classes="result-images-container"):
        img_output_sNN = gr.HTML(
            label="Network Diagram of Single Numbering Network",
        ) if output_format == "svg" else gr.Image(
            label="Network Diagram of Single Numbering Network"
        )
        img_output_dNN = gr.HTML(
            label="Network Diagram of Double Numbering Network",
        ) if output_format == "svg" else gr.Image(
            label="Network Diagram of Double Numbering Network"
        )

    # 处理函数
    image_input.change(
        fn=process_image,
        inputs=[image_input],
        outputs=[
            response_content, table_output, plantuml_output,
            img_output_sNN, img_output_dNN, terminal_output
        ],
        queue=True,
    )

# 启动应用
if __name__ == "__main__":
    # 启动应用
    demo.launch(share=True)
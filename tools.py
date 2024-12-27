from __future__ import annotations
from typing import *
import openai
import re
from pathlib import Path
from core import main
import yaml
import os
import subprocess
import time
import base64
from CONST import API_KEY
# BASE_URL = "https://api.moonshot.cn/v1"
BASE_URL = "https://api.openai.com/v1"
client = openai.OpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
)


def upload_and_get_answer(image_path):
    def _upload_files(files: List[str], purpose) -> List[Dict[str, Any]]:
        messages = []
        for file in files:
            file_object = client.files.create(file=Path(file), purpose=purpose)
            file_content = client.files.content(file_id=file_object.id).text
            messages.append({
                "role": "system",
                "content": file_content,
            })
        return messages

    print("------------------------------1、调用Kimi API将图片转换为YAML格式的Markdown------------------------------")
    prompt = [{
            "role": "system",
            "content":
                "你是人工智能助手，你更擅长中文和英文的对话。你会为用户提供安全，有帮助，"
                "准确的回答。同时，你会拒绝一切涉及恐怖主义，种族歧视，黄色暴力等问题的回答。"
                "你尽可能回复关键信息，避免废话。",
        },
        {
            "role": "user",
            "content":
                '''
                    请将图片中的内容转换为需要的YAML文件和markdown格式的表格,YAML文件请参考如下格式：
                    Activities:\n
                    - Id: A\n
                    Duration: 5\n
                    Activity: 'A"\n
                    Predecessors: []\n
                    Effort: 5\n
                    Resource: "Resource1"\n
                    - Id: B\n
                    Duration: 10\n
                    Activity: "B"\n
                    Predecessors: []\n
                    Effort: 10\n
                    Resource: "Resource2"\n
                    Resources:\n
                    - Id: Resource1\n
                    Pensum: 1.0\n
                    - Id: Resource2\n
                    Pensum: 1.0\n
                    
                    markdown格式的表格请参考如下格式：\n
                    ```markdown
                    | 作业 | 计划完成时间/天 | 紧前作业 | 作业 | 计划完成时间/天 | 紧前作业 |\n
                    |:-----:|:------------:|:--------:|:----:|:------------:|:-------:|\n
                    | A    | 5               |     -    | G    | 21              | B,E        |\n
                    | B    | 10              |     -    | H    | 35               | B,E          |\n
                    | C    | 11              |     -    | I    | 25               | B,E          |\n
                    | D    | 4               |     B    | J    | 15               | F,G,I          |\n
                    | E    | 4               |     A    | K    | 20               | F,G          |\n
                    | F    | 15               |     C,D    |      |                  |              |\n
                    ```
                '''
        },
    ]
    if "openai" in BASE_URL:
        # Function to encode the image
        def encode_image(image_path):
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        # Encode the image
        image_data = encode_image(image_path)
        messages = [
            *prompt,
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                    },
                ],
            },
        ]
    else:
        file_messages = _upload_files(files=["core.py", image_path], purpose="file-extract")
        messages = [
            *prompt,
            *file_messages,
        ]

    response = ""
    # 使用ChatCompletion API，启用流式输出
    if "openai" in BASE_URL:
        for chunk in client.chat.completions.create(
            model="chatgpt-4o-latest",
            messages=messages,
            stream=True
        ):
            delta = chunk.choices[0].delta
            if delta.content:
                response += delta.content
                print(delta.content, end='', flush=True)
                yield response
    else:
        for chunk in client.chat.completions.create(
            model="moonshot-v1-128k",
            messages=messages,
            stream=True
        ):
            delta = chunk.choices[0].delta
            if delta.content:
                response += delta.content
                print(delta.content, end='', flush=True)
                yield response


def get_yaml(markdown_content, yaml_path: Path = "__temp__/output_format.yaml"):
    print("------------------------------2、从回复中提取YAML内容------------------------------")
    time.sleep(1)
    # 使用正则表达式提取 YAML 内容
    yaml_pattern = re.compile(r'```yaml\n(.*?)\n```', re.DOTALL)
    yaml_match = yaml_pattern.search(markdown_content)
    if yaml_match:
        yaml_content = yaml_match.group(1)
        print("提取的YAML内容为：")
        print(yaml_content)
        # 将清理后的 YAML 内容保存到文件
        with open(yaml_path, 'w') as file:
            file.write(yaml_content)
        print(f"YAML文件已经保存至{yaml_path}")
        return yaml_content
    else:
        raise FileNotFoundError("未能提取出正确的YAML内容，请检查输入的Markdown内容是否正确。")


def get_md_chart(markdown_content):
    print("------------------------------3、从回复中提取markdown表格-----------------------------")
    time.sleep(1)
    # 使用正则表达式提取 Markdown 表格
    markdown_pattern = re.compile(r'```markdown\n(.*?)\n```', re.DOTALL)
    markdown_match = markdown_pattern.search(markdown_content)
    if markdown_match:
        markdown_table = markdown_match.group(1)
        print("提取的markdown表格为：\n")
        print(markdown_table)
        return markdown_table
    else:
        raise FileNotFoundError("未能提取出正确的Markdown表格，请检查输入的Markdown内容是否正确。")


def convert_yaml2uml(yaml_path: Path, puml_path: Path, network="double", quiet=False):
    if not quiet:
        print("------------------------------4、将YAML文件转换为UML图表定义------------------------------")
    uml_text, _ = main(Path(yaml_path), network=network, quiet=quiet)
    with open(puml_path, 'w') as file:
        file.write(uml_text)
    return uml_text


def convert_uml2pert(puml_path: Path, output_path: Path, output="svg"):
    if puml_path is None:
        puml_path = Path(r"__temp__/PUML_text_dNN.puml")
    jar_path = r"plantuml-1.2024.8.jar"
    command = ['java', '-jar', jar_path, '-t' + output, puml_path]
    img_path = Path(puml_path).parents[0] / f"PERT.{output}"
    try:
        result = subprocess.run(
            command, check=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, env=os.environ.copy()
        )
        if os.path.exists(output_path):
            os.remove(output_path)
        os.rename(img_path, output_path)
    except subprocess.CalledProcessError as e:
        print("Error:", e.stderr)
    except FileNotFoundError as e:
        print(f"Error: 系统找不到指定的文件，请检查Java和plantuml.jar是否正确安装和配置。{e}")


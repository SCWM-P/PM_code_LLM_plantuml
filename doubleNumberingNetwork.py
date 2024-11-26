from __future__ import annotations
from typing import *
import openai
import re
from pathlib import Path
from main.conversion import main, logging
import yaml
import os
import subprocess
import time
client = openai.OpenAI(
    base_url="https://api.moonshot.cn/v1",
    api_key="sk-o2r7caUcIecAst0pc06cS8tqvL0hAXSr6gxz3g8txSZyOre1",
)


def upload_and_get_answer(image_path):
    def _upload_files(files: List[str]) -> List[Dict[str, Any]]:
        messages = []
        for file in files:
            file_object = client.files.create(file=Path(file), purpose="file-extract")
            file_content = client.files.content(file_id=file_object.id).text
            messages.append({
                "role": "system",
                "content": file_content,
            })
        return messages

    print("------------------------------1、调用Kimi API将图片转换为YAML格式的Markdown------------------------------")
    file_messages = _upload_files(files=["main/conversion.py", image_path])
    messages = [
        *file_messages,
        {
            "role": "system",
            "content":
                "你是 Kimi，由 Moonshot AI 提供的人工智能助手，你更擅长中文和英文的对话。你会为用户提供安全，有帮助，"
                "准确的回答。同时，你会拒绝一切涉及恐怖主义，种族歧视，黄色暴力等问题的回答。Moonshot AI 为专有名词，"
                "不可翻译成其他语言。"
                "你尽可能回复关键信息，避免废话。",
        },
        {
            "role": "user",
            "content":
                '''
                    请将图片中的内容转换为这个代码需要的YAML文件和markdown格式的表格,YAML文件请参考如下格式：
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

    response = ""
    # 使用Kimi的ChatCompletion API，启用流式输出
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


def convert_yaml2uml(yaml_path: Path, txt_path: Path):
    print("------------------------------4、将YAML文件转换为UML图表定义------------------------------")
    logger = logging.getLogger(__name__)
    formats = "[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"
    logging.basicConfig(format=formats)
    logger.setLevel(logging.DEBUG)
    main(Path(yaml_path))
    with open(txt_path, 'r') as file:
        print("UML图表定义为：")
        f = file.read()
        print(f)
    return f


def convert_uml2pert(txt_path: Path, output="svg"):
    print("------------------------------5、将UML图表定义转换为PERT图并找出关键路径------------------------------")
    if txt_path is None:
        txt_path = r"__temp__/output.txt"
    jar_path = r"plantuml.jar"
    command = ['java', '-jar', jar_path, '-t' + output, txt_path]
    try:
        result = subprocess.run(
            command, check=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, env=os.environ.copy()
        )
        print(f"已输出图像，图像名称为PERT.{output}", result.stdout)
    except subprocess.CalledProcessError as e:
        print("Error:", e.stderr)
    except FileNotFoundError as e:
        print(f"Error: 系统找不到指定的文件，请检查Java和plantuml.jar是否正确安装和配置。{e}")


def calc_results(txt_path: Path):
    print("------------------------------6、输出关键路径与最短用时------------------------------")
    with open(txt_path, 'r') as file:
        content = file.read()
    # 使用正则表达式匹配所有map块和活动
    map_pattern = re.compile(
        r'map \d+ \{[^}]*\ earliest start => (\d+)\n[^}]* latest start => \d+\}'
    )
    activity_pattern = re.compile(
        r'(\d+) -\[thickness=4\]-> (\d+) : ([A-Z]) \(Id=[A-Z], D=(\d+), TF=(\d+), FF=(\d+)\)'
    )
    maps = map_pattern.findall(content)
    earliest_starts = {i // 2: int(start) for i, start in enumerate(maps)}

    activities = activity_pattern.findall(content)

    # 计算最早开始时间和最晚开始时间
    activity_details = []
    for activity in activities:
        activity_id, end_node_id, activity_label, duration, total_float, free_float = activity
        start_node_earliest_start = earliest_starts.get(int(activity_id) - 1, 0)
        end_node_earliest_start = earliest_starts.get(int(end_node_id) - 1, 0)
        activity_details.append(
            (activity_id, start_node_earliest_start, end_node_earliest_start, duration, total_float, free_float))

    # 计算关键路径和最短用时
    critical_path = []
    total_duration = 0
    for detail in activity_details:
        if detail[4] == '0':
            critical_path.append((detail[0], detail[3]))
        total_duration += int(detail[3])

    # 将活动ID映射到它们对应的标签
    activity_labels = {0: 'A', 1: 'B', 2: 'C', 3: 'D', 4: 'E', 5: 'F', 6: 'G', 7: 'H', 8: 'I', 9: 'J', 10: 'K'}
    critical_path_labels = [
        (activity_labels[int(activity_id)], int(duration))
        for activity_id, duration in critical_path
    ]
    # 按照它们在关键路径上的顺序连接起来
    critical_path_formatted = '→'.join([f"{label}({duration})" for label, duration in critical_path_labels])
    print(f"关键路径: {critical_path_formatted}")
    print(f"最短用时: {total_duration}")

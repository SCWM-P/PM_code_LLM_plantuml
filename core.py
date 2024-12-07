from pathlib import Path
import yaml
import copy
from typing import Optional


header = """
@startuml PERT
left to right direction
' Horizontal lines: -->, <--, <-->
' Vertical lines: ->, <-, <->
title Pert: Project Design"""
thickness = 5
footer = "@enduml"
ID = "Id"
PREDECESSORS = "Predecessors"
ACTIVITY = "Activity"
ACTIVITIES = "Activities"
EFFORT = "Effort"
OWNER = "Owner"
RESOURCE = "Resource"
RESOURCES = "Resources"
DURATION = "Duration"
PENSUM = "Pensum"


class Activity:
    def __init__(self, id, preprocedure: list[str], activity: str, effort, owner: str, resource: str, node=None):
        self.id = id
        self.Preprocedure = preprocedure
        self.Activity = activity
        self.Effort = effort
        self.Owner = owner
        self.Resource = resource
        self.ES = self.EF = self.LS = self.LF = self.TF = self.FF = 0
        self.node = node

    def __str__(self):
        return (f"ID: {self.id}, "
                f"Preprocedure: {self.Preprocedure}, "
                f"Activity:{self.Activity}, "
                f"Effort: {self.Effort}, "
                f"Owner:{self.Owner}, "
                f"Resource:{self.Resource}, "
                f"ES:{self.ES}, EF:{self.EF}, LS:{self.LS}, LF:{self.LF}, TF:{self.TF}, FF:{self.FF}\n")


class Node:
    def __init__(self, id, activity: Activity):
        self.id = id
        self.activity = activity
        self.in_node = []
        self.out_node = []

    def __str__(self):
        return (f"NodeID:{self.id}, in_node:{[node.id for node in self.in_node]},"
                f"out_node:{[node.id for node in self.out_node]}, Activity:{self.activity}")


class LinkedListNode:
    def __init__(self, value):
        self.value = value
        self.next = None


class LinkedList:
    def __init__(self, head=None):
        self.head = head

    def end(self):
        """返回链表尾部"""
        if not self.head:
            return Node
        node = self.head
        while node.next:
            node = node.next
        return node

    def append(self, next_node):
        """在链表尾部添加一个新的节点"""
        if not self.head:
            self.head = LinkedListNode(next_node)
        last_node = self.end()
        last_node.next = LinkedListNode(next_node)

    def get_nodes_value(self):
        """迭代得到链表中的所有节点"""
        if not self.head:
            return []
        nodes = [self.head.value]
        node = self.head
        while node.next:
            node = node.next
            nodes.append(node.value)
        return nodes

    def __str__(self):
        return "\n".join([node.id for node in self.get_nodes_value()])


def path_search(linked_list: LinkedList, next_nodes_func: callable = lambda x: x.out_node):
    """广度优先搜索所有路径"""
    pathList = [linked_list]

    def _breadth_search(pathlist: list[LinkedList]):
        for path in pathlist:
            last_node = path.end().value
            next_nodes = next_nodes_func(last_node)
            if not next_nodes:
                continue
            else:
                if_add = False
                original_path = copy.deepcopy(path)
                for node in next_nodes:
                    if not if_add:
                        path.append(node)
                        if_add = True
                    else:
                        new_path = copy.deepcopy(original_path)
                        new_path.append(node)
                        pathList.append(new_path)

    while not all([path.end().value.id == "End" for path in pathList]):
        _breadth_search(pathList)
    return pathList


def core_calculate(yaml_path: Path):
    with open(yaml_path, 'r') as file:
        data = yaml.safe_load(file)

    # 构建Activity字典与Node字典
    activity_dict = {
        activity[ID]: Activity(
            activity[ID], activity.get(PREDECESSORS, []), activity.get(ACTIVITY, ""),
            activity[EFFORT], activity.get(OWNER, ""), activity.get(RESOURCE, "")
        ) for activity in data[ACTIVITIES]
    }
    activity_dict["Start"] = Activity("Start", [], "Start", 0, "", "")
    activity_dict["End"] = Activity("End", [], "End", 0, "", "")
    node_dict = {
        activity.id: Node(activity.id, activity)
        for activity in activity_dict.values()
    }
    node_dict["Start"] = Node("Start", activity_dict["Start"])
    node_dict["End"] = Node("End", activity_dict["End"])
    # 绑定Activity与Node
    for activity in activity_dict.values():
        activity.node = node_dict[activity.id]

    # 构建节点之间的关系
    # 绑定入度
    for id in activity_dict.keys():
        if id == "End" or id == "Start":
            continue
        else:
            if activity_dict[id].Preprocedure:
                for pre in activity_dict[id].Preprocedure:
                    node_dict[id].in_node.append(node_dict[pre])
                    node_dict[pre].out_node.append(node_dict[id])
            else:
                node_dict["Start"].out_node.append(node_dict[id])
                node_dict[id].in_node.append(node_dict["Start"])
    # 绑定出度
    for id in activity_dict.keys():
        if id == "End" or id == "Start":
            continue
        else:
            if not node_dict[id].out_node:
                node_dict[id].out_node.append(node_dict["End"])
                node_dict["End"].in_node.append(node_dict[id])

    # 计算ES，EF，LS，LF的递归函数
    def calculate_ES_and_EF(node: Node):
        if node.id == "Start":
            node.activity.ES = 0
            node.activity.EF = node.activity.Effort + node.activity.ES
            return 0
        else:
            in_node_ES = []
            for pre_activity in node.in_node:
                pre_activity.activity.ES = calculate_ES_and_EF(pre_activity)
                pre_activity.activity.EF = pre_activity.activity.ES + pre_activity.activity.Effort
                in_node_ES.append(pre_activity.activity.EF)
            return max(in_node_ES)

    def calculate_LS_and_LF(node: Node):
        if node.id == "End":
            node.activity.LF = node.activity.EF
            node.activity.LS = node.activity.LF - node.activity.Effort
            return node.activity.LF
        else:
            out_node_LS = []
            for next_node in node.out_node:
                next_node.activity.LF = calculate_LS_and_LF(node_dict[next_node.activity.id])
                next_node.activity.LS = next_node.activity.LF - next_node.activity.Effort
                out_node_LS.append(next_node.activity.LS)
            return min(out_node_LS)

    # 递归计算ES，EF，LS，LF
    activity_dict["End"].ES = activity_dict["End"].EF = calculate_ES_and_EF(node_dict["End"])
    activity_dict["Start"].LS = activity_dict["Start"].LF = calculate_LS_and_LF(node_dict["Start"])
    for activity in activity_dict.values():
        activity.TF = activity.LS - activity.ES
        if activity.node.out_node:
            activity.FF = min(
                [
                    next_node.activity.ES - activity.EF
                    for next_node in activity.node.out_node
                ]
            )
    # 找到所有路径
    path_list = path_search(
        LinkedList(
            LinkedListNode(
                node_dict["Start"]
            )
        )
    )
    # 找到关键路径
    key_path_list = []
    for path in path_list:
        if all([node.activity.TF == 0 for node in path.get_nodes_value()]):
            key_path_list.append(path)

    return activity_dict, node_dict, path_list, key_path_list


def double_Numbering_Network(activity_dict, node_dict, path_list, key_path_list):
    class _MapNode:
        """
        双代号网络节点
        # 节点的命名规则
        1. 起始节点为"Start"， 终点节点为"End"
        2. 若节点的入度为虚工作，则按照出度对应的ID特殊标识得到，例如"virtual_A*"
        3. 若节点的入度为实工作，则直接使用ID，例如"A"
        """
        def __init__(self, map_id, earliest_start, latest_start, map_in_node=None, map_out_node=None):
            if map_out_node is None:
                self.map_out_node = []
            if map_in_node is None:
                self.map_in_node = []
            self.map_id = map_id
            self.earliest_start = earliest_start
            self.latest_start = latest_start

        def __str__(self):
            string = f"""map {self.map_id} {{
    earliest start => {self.earliest_start}
    latest start => {self.latest_start}
}}"""
            return string

    class _MapEdge:
        """
        双代号网络边
        # 边的命名规则
        1. 若边为虚工作，则用起点（紧前工作）与终点（实际工作）命名。例如: C的紧前工作为A，B，两个虚工作边分别为"A-C"，"B-C"
        2. 若边为实工作，则用实工作的ID命名。例如: 实工作C的边为"C"
        3. 仅当边为关键路径上的边时，边被thickness加重
        """
        def __init__(self, start_node: _MapNode, end_node: _MapNode, activity: Optional[Activity], thickness=0, dashed=False):
            self.start_node = start_node
            self.end_node = end_node
            self.thickness = thickness
            self.activity = activity
            self.dashed = dashed

        def attribution(self):
            string = []
            if self.dashed:
                string.append("dashed")
            if self.thickness:
                string.append(f"thickness={self.thickness}")
            return f"[{','.join(string)}]" if string else ""

        def __str__(self):
            if not self.dashed:
                return (f"{self.start_node.map_id} -{self.attribution()}-> {self.end_node.map_id} : "
                        f"{self.activity.Activity} (Id={self.activity.id}, D={self.activity.Effort}, "
                        f"TF={self.activity.TF}, FF={self.activity.FF})")
            else:
                return f"{self.start_node.map_id} -{self.attribution()}-> {self.end_node.map_id}"

    map_node_dict = {
        "Start": _MapNode(0, 0, 0),
        "End": _MapNode("End", node_dict["End"].activity.ES, node_dict["End"].activity.LS)
    }
    map_edge_dict = {}
    for node in node_dict.values():
        if node.id == "Start":
            continue
        if not node.in_node:
            map_node_dict[str(node.id)] = _MapNode(str(node.id), node.activity.ES, node.activity.LS)
            map_edge_dict[str(node.id)] = _MapEdge(
                map_node_dict["Start"],
                map_node_dict[str(node.id)], node.activity
            )
        elif len(node.in_node) == 1:
            pre_node = node.in_node[0]
            map_node_dict[str(node.id)] = _MapNode(str(node.id), node.activity.ES, node.activity.LS)
            map_edge_dict[str(node.id)] = _MapEdge(
                map_node_dict[str(pre_node.id)],
                map_node_dict[str(node.id)], node.activity
            )
        elif len(node.in_node) > 1:
            for pre_node in node.in_node:
                map_node_dict[f"virtual_{node.id}"] = _MapNode(f"virtual_{node.id}", node.activity.ES, node.activity.LS)
                map_edge_dict[f"{pre_node.id}-{node.id}"] = _MapEdge(
                    map_node_dict[str(pre_node.id)],
                    map_node_dict[f"virtual_{node.id}"], None, dashed=True
                )
            map_node_dict[str(node.id)] = _MapNode(str(node.id), node.activity.ES, node.activity.LS)
            map_edge_dict[str(node.id)] = _MapEdge(
                map_node_dict[f"virtual_{node.id}"],
                map_node_dict[str(node.id)], node.activity
            )
    # 为关键路径上的边加粗
    for key_path in key_path_list:
        key_node = key_path.head
        while key_node.next:
            next_node = key_node.next
            if len(next_node.value.in_node) > 1:
                map_edge_dict[f"{key_node.value.id}-{next_node.value.id}"].thickness = thickness
                map_edge_dict[f"{next_node.value.id}"].thickness = thickness
            else:
                map_edge_dict[f"{next_node.value.id}"].thickness = thickness
            key_node = next_node
    return map_node_dict, map_edge_dict


def single_Numbering_Network(activity_dict, node_dict, path_list, key_path_list):
    class _MapNode:
        """
        单代号网络节点
        # 节点的命名规则
        1. 起始节点为"Start"， 终点节点为"End"
        2. 节点的ID为实工作的ID
        """
        def __init__(
                self, map_id, earliest_start, latest_start,
                earliest_finish, latest_finish,
                total_float, free_float, activity: Activity,
                map_in_node=None, map_out_node=None
        ):
            if map_out_node is None:
                self.map_out_node = []
            if map_in_node is None:
                self.map_in_node = []
            self.map_id = map_id
            self.activity = activity
            self.earliest_start = earliest_start
            self.latest_start = latest_start
            self.earliest_finish = earliest_finish
            self.latest_finish = latest_finish
            self.total_float = total_float
            self.free_float = free_float

        def __str__(self):
            string = f"""map {self.map_id} {{
    ES => {self.earliest_start}
    LS => {self.latest_start}
    EF => {self.earliest_finish}
    LF => {self.latest_finish}
    TF => {self.total_float}
    FF => {self.free_float}
}}"""
            return string

    class _MapEdge:
        """
        单代号网络边
        # 边的命名规则
        1. 若边为实工作，则用实工作的ID命名。例如: 实工作A的边为"A"
        2. 仅当边为关键路径上的边时，边被thickness加重
        """
        def __init__(self, start_node: _MapNode, end_node: _MapNode, thickness=0):
            self.start_node = start_node
            self.end_node = end_node
            self.thickness = thickness

        def attribution(self):
            if self.thickness:
                return f"[thickness={self.thickness}]"
            else:
                return ""

        def __str__(self):
            return f"{self.start_node.map_id} -{self.attribution()}-> {self.end_node.map_id}"

    start_activity = activity_dict["Start"]
    map_node_dict = {
        "Start": _MapNode(
            start_activity.id, start_activity.ES, start_activity.LS,
            start_activity.EF, start_activity.LF, start_activity.TF,
            start_activity.FF, start_activity
        ),
    }
    map_edge_dict = {}
    for node in node_dict.values():
        map_node_dict[str(node.id)] = _MapNode(
            str(node.id), node.activity.ES, node.activity.LS,
            node.activity.EF, node.activity.LF,
            node.activity.TF, node.activity.FF, node.activity
        )
        for pre_node in node.in_node:
            map_edge_dict[f"{pre_node.id}-{node.id}"] = _MapEdge(
                map_node_dict[str(pre_node.id)],
                map_node_dict[str(node.id)]
            )
    # 为关键路径上的边加粗
    for key_path in key_path_list:
        key_node = key_path.head
        while key_node.next:
            next_node = key_node.next
            map_edge_dict[f"{key_node.value.id}-{next_node.value.id}"].thickness = thickness
            key_node = next_node
    return map_node_dict, map_edge_dict


def main(path: Path, network="double", quiet=False):
    activityList, nodeDict, pathList, keyPathList = core_calculate(path)
    if network == "single":
        mapNodeDict, mapEdgeDict = single_Numbering_Network(activityList, nodeDict, pathList, keyPathList)
    elif network == "double":
        mapNodeDict, mapEdgeDict = double_Numbering_Network(activityList, nodeDict, pathList, keyPathList)
    else:
        raise ValueError("network must be 'single' or 'double'")
    if not quiet:
        # 输出结果
        print("所有路径：")
        for path in pathList:
            print(" -> ".join([f"{i.id}(TF={i.activity.TF})" for i in path.get_nodes_value()]), end="\n")
        print("关键路径：")
        for key_path in keyPathList:
            print(" -> ".join([str(i.id) for i in key_path.get_nodes_value()]))
        print("最小工期为：", nodeDict["End"].activity.ES)
        # print("双代号网络节点：")
        # for node in mapNodeDict.values():
        #     print(node)
        # print("双代号网络边：")
        # for edge in mapEdgeDict.values():
        #     print(edge)
    uml_text = (header + (" of Double Numbering Network\n" if network == "double" else " of Single Numbering Network\n") +
                "\n".join([str(i) for i in mapNodeDict.values()]) +
                "\n" + "\n".join([str(i) for i in mapEdgeDict.values()]) +
                "\n" + footer)
    output = {
        "activityList": activityList,
        "nodeDict": nodeDict,
        "pathList": pathList,
        "keyPathList": keyPathList,
        "mapNodeDict": mapNodeDict,
        "mapEdgeDict": mapEdgeDict,
    }
    return uml_text, output


if __name__ == '__main__':
    unlText = main(Path(r"D:\Projects\ProjectManagement\main\tests\artefacts\AoA.yaml"))
    print(unlText)

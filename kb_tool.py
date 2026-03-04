"""知识库工具模块。

使用 Strands @tool 装饰器定义知识库文件读取工具，
供 Agent 按需调用以获取 Kiro 技术支持相关知识。
"""

import os

from strands import tool

from config import KB_DIR


def _scan_kb_files() -> list[tuple[str, str]]:
    """扫描知识库目录，返回 (文件名, 首行摘要) 列表。"""
    summaries: list[tuple[str, str]] = []
    if not os.path.isdir(KB_DIR):
        return summaries
    for fname in sorted(os.listdir(KB_DIR)):
        if not fname.endswith(".md"):
            continue
        filepath = os.path.join(KB_DIR, fname)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
            summaries.append((fname, first_line))
        except Exception:
            summaries.append((fname, "(无法读取摘要)"))
    return summaries


def _build_tool_docstring() -> str:
    """构建包含可用文件列表的工具描述。"""
    base = "读取知识库文件内容，按需调用以获取特定主题的详细信息。\n\n可用文档:\n"
    entries = _scan_kb_files()
    if entries:
        for fname, summary in entries:
            base += f"- {fname}: {summary}\n"
    else:
        base += "- (暂无可用文档)\n"
    base += "\nArgs:\n    filename: 知识库文件名，例如 KB_1.md"
    return base


@tool
def read_kb_file(filename: str) -> str:
    """读取知识库文件内容。"""
    filepath = os.path.join(KB_DIR, filename)
    if not os.path.isfile(filepath):
        return f"错误: 知识库文件 '{filename}' 不存在。请检查文件名是否正确。"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"错误: 读取文件 '{filename}' 时发生异常: {e}"


# 动态更新 tool_spec 中的 description，列出所有可用的知识库文件及主题摘要
read_kb_file._tool_spec["description"] = _build_tool_docstring()

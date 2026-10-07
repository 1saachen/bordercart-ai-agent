"""核心 Agent 版边界合同：只保留三 Agent、RAG 与 Personal Skill。"""

import ast
import inspect

import pytest

from app.application.agents import main_agent, orchestrator, search_agent, selected_skill, trade_agent
from app.application.agents import personal_skill_context
from app.application.tools import capability_tools, task_dispatch_tool


@pytest.mark.parametrize(
    "module",
    [main_agent, orchestrator, search_agent, trade_agent, selected_skill, personal_skill_context,
     capability_tools, task_dispatch_tool],
)
def test_core_agent_modules_do_not_import_optional_governance(module):
    source = inspect.getsource(module)
    tree = ast.parse(source)
    forbidden = (
        "application.harness",
        "infrastructure.harness",
        "semantic_cache",
        "prompt_registry",
        "capability_registry",
        "web_search_tool",
        "tavily",
    )
    imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    imports += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
    assert not any(any(name in item for name in forbidden) for item in imports), (module.__name__, imports)

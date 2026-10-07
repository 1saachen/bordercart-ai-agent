"""核心运行时组合测试：三 Agent + 两类 RAG + Personal Skill。"""

from pydantic import BaseModel

from agentscope.credential import OpenAICredential
from agentscope.message import TextBlock
from agentscope.model import ChatModelBase, ChatResponse


class FakeChatModel(ChatModelBase):
    """不发起网络请求的 AgentScope 模型替身。"""

    class Parameters(BaseModel):
        pass

    def __init__(self):
        super().__init__(
            credential=OpenAICredential(api_key="test-key"),
            model="fake-core-model",
            parameters=self.Parameters(),
            stream=False,
        )

    async def _call_api(self, model_name, messages, tools=None, tool_choice=None, **kwargs):
        return ChatResponse(content=[TextBlock(text="ok")], is_last=True)


def _core_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("QDRANT_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)


async def test_core_container_constructs_three_agents_and_rag(monkeypatch, tmp_path):
    _core_environment(monkeypatch, tmp_path)
    fake = lambda *args, **kwargs: FakeChatModel()
    monkeypatch.setattr("app.application.agents.main_agent.create_chat_model", fake)
    monkeypatch.setattr("app.application.agents.search_agent.create_chat_model", fake)
    monkeypatch.setattr("app.application.agents.trade_agent.create_chat_model", fake)

    from agentscope.rag import KnowledgeBase
    from app.application.agents.main_agent import MainAgentFactory
    from app.application.agents.search_agent import SearchAgentFactory
    from app.application.agents.trade_agent import TradeAgentFactory
    from app.composition import build_container
    from app.infrastructure.buyer_skills import BuyerSkillStore
    from app.infrastructure.vector.qdrant_product_index import QdrantProductIndex

    container = await build_container()
    try:
        factory = container.orchestrator._sessions._main_factory
        assert isinstance(factory, MainAgentFactory)
        assert isinstance(factory._search_factory, SearchAgentFactory)
        assert isinstance(factory._trade_factory, TradeAgentFactory)
        assert isinstance(container.vector_index, QdrantProductIndex)
        assert container.vector_index._collection == container.settings.qdrant_collection
        assert isinstance(container.knowledge_base, KnowledgeBase)
        assert isinstance(factory.buyer_skill_store, BuyerSkillStore)

        main = factory.build()
        search = factory._search_factory.build()
        trade = factory._trade_factory.build()
        assert main.name and search.name and trade.name
        search_tool_names = {tool.name for tool in factory._search_factory.build_tools()}
        assert {"product_search_tool", "category_insight_tool"} <= search_tool_names
    finally:
        await container.shutdown()


async def test_personal_skill_store_is_buyer_scoped_in_core_container(monkeypatch, tmp_path):
    _core_environment(monkeypatch, tmp_path)
    from app.composition import build_container
    container = await build_container()
    try:
        store = container.orchestrator._sessions._main_factory.buyer_skill_store
        alice = store.save("alice", "验货", "购物前检查", "检查材质和尺寸")
        assert store.load("alice", alice["id"], alice["version"])["body"] == "检查材质和尺寸"
        try:
            store.load("bob", alice["id"], alice["version"])
        except LookupError:
            pass
        else:
            raise AssertionError("个人 Skill 必须按买家隔离")
    finally:
        await container.shutdown()

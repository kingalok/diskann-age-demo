# langgraph_react_agent1.py
import os
import asyncio
import signal
import atexit
from typing import Optional
from dotenv import load_dotenv

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
load_dotenv()
#MCP_SCRIPT = os.environ.get("AZURE_PG_MCP_PATH", os.path.abspath("./azure_postgresql_mcp.py"))
MCP_SCRIPT = "/Users/Alok_Sharma/Documents/myrepo/azure-postgresql-mcp/src/azure_postgresql_mcp.py"
DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-35-turbo")

_GLOBAL_MCP_CLIENT: Optional[MultiServerMCPClient] = None

async def _build_graph():
    global _GLOBAL_MCP_CLIENT
    llm = init_chat_model(f"azure_openai:{DEPLOYMENT}", azure_deployment=DEPLOYMENT)
    _GLOBAL_MCP_CLIENT = MultiServerMCPClient({
        "azure-postgresql-mcp": {
            "command": "python",
            "args": [MCP_SCRIPT],
            "transport": "stdio",
        }
    })
    tools = await _GLOBAL_MCP_CLIENT.get_tools()
    g = create_react_agent(llm, tools)
    setattr(g, "_mcp_client", _GLOBAL_MCP_CLIENT)
    return g

# -------- Export for langgraph dev --------
# Must be a Graph or a (async) factory function returning a Graph.
async def graph():
    return await _build_graph()

# -------- Standalone runner (optional) --------
async def _shutdown():
    global _GLOBAL_MCP_CLIENT
    if _GLOBAL_MCP_CLIENT is not None:
        try:
            await _GLOBAL_MCP_CLIENT.close()
        finally:
            _GLOBAL_MCP_CLIENT = None

def _install_signal_handlers(loop):
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown()))
        except NotImplementedError:
            pass

atexit.register(lambda: asyncio.run(_shutdown()) if asyncio.get_event_loop_policy().get_event_loop().is_running() is False else None)

async def _main():
    g = await graph()
    user_msg = "Using the Azure PostgreSQL MCP tools, list schemas; then run SELECT current_database();"
    res = await g.ainvoke({"messages": [{"role": "user", "content": user_msg}]})
    print("\n=== Agent Result ===")
    print(res)
    await _shutdown()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _install_signal_handlers(loop)
    loop.run_until_complete(_main())

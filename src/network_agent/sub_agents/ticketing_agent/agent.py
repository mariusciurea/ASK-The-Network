"""Ticketing agent module"""

from google.adk.agents import LlmAgent

from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.skills import load_skill_from_dir

from src.core.settings import settings
from src.network_agent.sub_agents.ticketing_agent.prompt import TICKETING_INSTRUCTIONS


ticketing_skill = load_skill_from_dir(f"{settings.AGENT_DIR}/sub_agents/ticketing_agent/skills/ticketing-skill")
ticketing_skill_toolset = SkillToolset(
    skills=[ticketing_skill],
    additional_tools=[]
)

mcp_toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=settings.MCP_URL,
    ),
    tool_filter=[
        "get_tickets_info",
        "send_sql_command"
    ],

)

ticketing_agent = LlmAgent(
    name="ticketing_agent",
    model=settings.MODEL_NAME,
    description="Get data about tickets",
    instruction=TICKETING_INSTRUCTIONS,
    tools=[
        ticketing_skill_toolset,
        mcp_toolset,
    ],
)
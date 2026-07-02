"""Router agent module"""

from google.adk.agents import LlmAgent
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.skills import load_skill_from_dir

from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from backend.network_agent.sub_agents.common_tools import send_sql_command

from backend.core.settings import settings
from backend.network_agent.sub_agents.radio_agent.prompt import RADIO_INSTRUCTIONS


radio_skill = load_skill_from_dir(f"{settings.AGENT_DIR}/sub_agents/radio_agent/skills/radio-skill")
radio_skill_toolset = SkillToolset(
    skills=[radio_skill],
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

radio_agent = LlmAgent(
    name="radio_agent",
    model=settings.MODEL_NAME,
    description="Convert user prompt in SQL queries",
    instruction=RADIO_INSTRUCTIONS,
    tools=[
        radio_skill_toolset,
        send_sql_command,
        # mcp_toolset,

    ],
)
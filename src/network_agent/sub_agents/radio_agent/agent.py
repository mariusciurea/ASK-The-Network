"""Radio agent module"""

from google.adk.agents import LlmAgent
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.skills import load_skill_from_dir

from src.network_agent.sub_agents.common_tools import send_sql_command

from src.core.settings import settings
from src.network_agent.sub_agents.radio_agent.prompt import RADIO_INSTRUCTIONS


radio_skill = load_skill_from_dir(f"{settings.AGENT_DIR}/sub_agents/radio_agent/skills/radio-skill")
radio_skill_toolset = SkillToolset(
    skills=[radio_skill],
    additional_tools=[]
)

radio_agent = LlmAgent(
    name="radio_agent",
    model=settings.MODEL_NAME,
    description="Convert user prompt in SQL queries",
    instruction=RADIO_INSTRUCTIONS,
    tools=[
        radio_skill_toolset,
        send_sql_command,
    ],
)
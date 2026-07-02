from google.adk.agents import Agent

from backend.network_agent.sub_agents.ticketing_master.prompt import TICKETING_MASTER_INSTRUCTIONS
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

from backend.core.settings import settings

from backend.network_agent.sub_agents.common_tools import send_sql_command

ticketing_skill = load_skill_from_dir(f"{settings.AGENT_DIR}/sub_agents/ticketing_master/skills/ticketing-master-skill")
ticketing_skill_toolset = SkillToolset(
    skills=[ticketing_skill],
)

ticketing_master_agent = Agent(
    name="ticketing_master",
    model=settings.MODEL_NAME,
    description="An agent that handles ticketing related questions",
    instruction=TICKETING_MASTER_INSTRUCTIONS,
    tools=[ticketing_skill_toolset, send_sql_command],
)
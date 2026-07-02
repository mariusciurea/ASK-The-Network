"""Planning agent module"""

from google.adk.agents import LlmAgent
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.skills import load_skill_from_dir

from backend.network_agent.sub_agents.common_tools import send_sql_command

from backend.core.settings import settings
from backend.network_agent.sub_agents.planning_agent.prompt import PLANNING_INSTRUCTIONS
from backend.network_agent.sub_agents.planning_agent.tools import calculate_free_ips

planning_skill = load_skill_from_dir(f"{settings.AGENT_DIR}/sub_agents/planning_agent/skills/planning-skill")
planning_skill_toolset = SkillToolset(
    skills=[planning_skill],
    additional_tools=[]
)

planning_agent = LlmAgent(
    name="planning_agent",
    model=settings.MODEL_NAME,
    description="Generate free loopback IP addresses in a given subnet",
    instruction=PLANNING_INSTRUCTIONS,
    tools=[
        planning_skill_toolset,
        send_sql_command,
        calculate_free_ips
    ],
)
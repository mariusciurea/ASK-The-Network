"""Router agent module"""

from google.adk.agents import LlmAgent
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.skills import load_skill_from_dir
from google.adk.tools import agent_tool

from src.network_agent.sub_agents.radio_agent.agent import radio_agent
from src.network_agent.sub_agents.planning_agent.agent import planning_agent
from src.network_agent.sub_agents.ticketing_agent.agent import ticketing_agent

from src.core.settings import settings
from src.network_agent.prompt import ROOT_INSTRUCTIONS


root_skill = load_skill_from_dir(f"{settings.AGENT_DIR}/skills/root-skill")
root_skill_toolset = SkillToolset(
    skills=[root_skill],
    additional_tools=[]
)

root_agent = LlmAgent(
    name="network_agent",
    model=settings.MODEL_NAME,
    description="An agent that orchestrates multiple sub-agents to manage and troubleshoot "
                "network configurations, including radio network elements and security protocols.",
    instruction=ROOT_INSTRUCTIONS,
    tools=[
        root_skill_toolset,
        agent_tool.AgentTool(radio_agent),
        agent_tool.AgentTool(planning_agent),
        agent_tool.AgentTool(ticketing_agent),

    ],
    # sub_agents=[radio_agent], #
)
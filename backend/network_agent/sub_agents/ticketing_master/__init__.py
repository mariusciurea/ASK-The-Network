"""Ticketing master agent package.

The agent is also exposed as `root_agent` so it can be evaluated on its own,
without going through the router:

    adk eval backend/network_agent/sub_agents/ticketing_master \
        backend/network_agent/sub_agents/ticketing_master/eval/ticketing_master.evalset.json
"""

from backend.network_agent.sub_agents.ticketing_master.agent import ticketing_master_agent

root_agent = ticketing_master_agent

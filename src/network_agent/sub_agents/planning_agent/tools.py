"""Tools for planning agent"""

import ipaddress
import json
from logging import getLogger
from google.adk.tools import ToolContext

logger = getLogger(__name__)

ARTIFACT_NAME = "sql_command_output.json"

async def calculate_free_ips(
    number_of_addresses: int,
    subnet: str,
    used_loopback_ips: list[str],
    tool_context: ToolContext,
) -> list[str]:
    """
    Return the requested number of free IP addresses from a subnet.

    If send_sql_command stored the complete SQL result as an artifact,
    use that artifact. Otherwise, use the list passed by the agent.
    """

    # Try to load the full SQL result from the artifact.
    logger.info("Trying to load artifact")

    try:
        artifact = await tool_context.load_artifact(ARTIFACT_NAME)

        if artifact is not None:
            rows = json.loads(
                artifact.inline_data.data.decode("utf-8")
            )

            logger.info("Artifact loaded")

            used_loopback_ips = [
                row["loop_ip"]
                for row in rows
                if row.get("loop_ip")
            ]

    except Exception as e:
        logger.exception(e)

    network = ipaddress.ip_network(subnet)

    used_ips = {
        ipaddress.ip_address(ip)
        for ip in used_loopback_ips
    }

    free_ips = []

    for host in network.hosts():
        if host not in used_ips:
            free_ips.append(str(host))

            if len(free_ips) >= number_of_addresses:
                break

    return free_ips
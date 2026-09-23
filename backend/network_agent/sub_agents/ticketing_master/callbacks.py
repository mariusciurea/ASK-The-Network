"""Callbacks wiring the semantic guard into the ticketing_master agent.

The instruction tells the model what to do; this callback makes sure a query
that ignores it never reaches the database. The rejection is returned as the
tool result, so the agent sees the reason and can correct itself in the same
turn instead of failing the conversation.
"""

from logging import getLogger
from typing import Any, Optional

from google.adk.tools import BaseTool, ToolContext

from backend.core.sql_safety import UnsafeSQLError
from backend.data_models.models import SQLCommandResult
from backend.network_agent.sub_agents.ticketing_master.sql_guard import guard_sql


logger = getLogger(__name__)
sql_command_logger = getLogger("audit.sql.commands")

GUARDED_TOOL = "send_sql_command"


def validate_sql_before_execution(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> Optional[dict]:
    """Validate free SQL against the semantic layer before it is executed.

    Args:
        tool: The tool the agent is about to call.
        args: Arguments of the call. `sql_query` is rewritten in place when the
            query needs a bounded LIMIT.
        tool_context: ADK tool context.

    Returns:
        None to let the call proceed, or a failed SQLCommandResult that replaces
        the tool call when the query is rejected.
    """

    if tool.name != GUARDED_TOOL:
        return None

    sql_query = args.get("sql_query", "")

    try:
        guarded_query = guard_sql(sql_query)
    except UnsafeSQLError as error:
        sql_command_logger.warning(f"Rejected SQL command: {sql_query} | reason: {error}")
        return SQLCommandResult.failure(
            f"The query was rejected before execution: {error} "
            f"Correct the query, or use run_metric and lookup_column_values instead.",
            sql_query=sql_query,
        ).model_dump()

    if guarded_query != sql_query:
        logger.info("Query rewritten to stay within the row limit.")
        args["sql_query"] = guarded_query

    return None

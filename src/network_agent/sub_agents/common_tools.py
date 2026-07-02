"""Tools for all sub-agents"""

import json
from logging import getLogger

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from google.genai.types import Part
from google.adk.tools import ToolContext

from src.data_models.models import SQLCommandResult
from src.database.db import engine

from src.core.settings import settings

from typing import Any


logger = getLogger(__name__)
sql_command_logger = getLogger("audit.sql.commands")
sql_result_logger = getLogger("audit.sql.results")


async def _save_artifact(sql_query_response: list[dict[str, Any]], tool_context: ToolContext) -> None:
    """Save artifact"""

    artifact_filename = "sql_command_output.json"
    mime_type = "application/json"

    bytes_query_response = json.dumps(sql_query_response, indent=2).encode("utf-8")

    artifact_content = Part.from_bytes(
        data=bytes_query_response,
        mime_type=mime_type
    )
    logger.info(
        "Saving artifact with %d rows",
        len(sql_query_response),
    )
    await tool_context.save_artifact(artifact_filename, artifact_content)


async def send_sql_command(sql_query: str, tool_context: ToolContext):
    """Execute a SQL command using the configured database connection.

      Args:
          sql_query: Raw SQL query to execute.
          tool_context: ToolContext object - context of the send_sql_command tool

      Returns:
          SQLCommandResult with either returned rows or error details.
    """



    if not sql_query:
        return SQLCommandResult.failure("sql_query parameter should not be empty")

    try:
        with engine.connect() as connection:
            sql_command_logger.info(f"Sending SQL command: {sql_query}")
            result = connection.execute(text(sql_query))

            if result.returns_rows:
                rows = [dict(row) for row in result.mappings().all()]

                if len(rows) > settings.MAX_ROWS:
                    await _save_artifact(rows, tool_context)
                    sql_result_logger.info(f"rows: {rows[0:settings.MAX_ROWS]}")
                    return SQLCommandResult.success(rows=rows[0:settings.MAX_ROWS])

                sql_result_logger.info(f"rows: {rows}")
                return SQLCommandResult.success(rows=rows)
    except SQLAlchemyError as e:
        logger.error(str(e))
        return SQLCommandResult.failure(str(e))

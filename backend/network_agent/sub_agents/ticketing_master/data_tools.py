"""Deterministic data access tools for the ticketing_master agent.

Text-to-SQL is the fallback, not the default. The tools here answer the
recurring questions with SQL that is written once, in the semantic layer, and
parameterized in code - so the same question always produces the same query:

* `describe_schema`       - pulls schema details on demand, keeping the
                            always-on instruction small
* `lookup_column_values`  - turns the user's wording into a canonical value
* `get_ticket`            - single ticket by number
* `run_metric`            - the named metrics of the semantic layer
"""

from datetime import datetime
from difflib import get_close_matches
from logging import getLogger
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from google.adk.tools import ToolContext

from backend.core.serialization import json_safe_rows
from backend.core.settings import settings
from backend.data_models.models import SQLCommandResult
from backend.database.db import engine
from backend.network_agent.sub_agents.common_tools import log_result_rows, save_rows_artifact
from backend.network_agent.sub_agents.ticketing_master.semantic_layer import (
    MetricSpec,
    SemanticLayer,
    load_semantic_layer,
)
from backend.network_agent.sub_agents.ticketing_master import value_index


logger = getLogger(__name__)
sql_command_logger = getLogger("audit.sql.commands")
sql_result_logger = getLogger("audit.sql.results")

DATE_INPUT_FORMAT = "%Y-%m-%d"
MAX_LOOKUP_RESULTS = 15


def describe_schema(topic: str) -> dict[str, Any]:
    """Return schema details that are not part of the standing instruction.

    Args:
        topic: One of 'columns', 'values', 'groups', 'metrics', 'examples',
            'rules', 'limitations'.

    Returns:
        A dictionary with the requested documentation as markdown.
    """

    layer = load_semantic_layer()

    try:
        return {"status": "success", "topic": topic, "content": layer.render_topic(topic)}
    except ValueError as error:
        return {"status": "failure", "error": str(error)}


def lookup_column_values(column: str, search_term: str = "") -> dict[str, Any]:
    """Resolve a user's wording to the values that really exist in a column.

    Always call this before filtering subject, loc_identifier or
    network_element_identifier on a term taken from the user's question.

    Args:
        column: Column to inspect: 'subject', 'loc_identifier' or
            'network_element_identifier'.
        search_term: Optional term to match. Empty returns the most frequent values.

    Returns:
        A dictionary with the matching values, their ticket counts and whether
        the match is exact.
    """

    layer = load_semantic_layer()

    try:
        rows = value_index.distinct_values(column, layer)
    except ValueError as error:
        return {"status": "failure", "error": str(error)}
    except SQLAlchemyError as error:
        logger.error("Value lookup failed for column '%s': %s", column, error)
        return {"status": "failure", "error": f"The value index is unavailable: {error}"}

    if not search_term:
        return {
            "status": "success",
            "column": column,
            "total_distinct_values": len(rows),
            "matches": rows[:MAX_LOOKUP_RESULTS],
            "note": "Most frequent values. Pass a search_term to narrow the list.",
        }

    term = search_term.strip().casefold()
    values = [str(row["value"]) for row in rows]
    counts = {str(row["value"]): row["ticket_count"] for row in rows}

    exact = [value for value in values if value.casefold() == term]
    partial = [value for value in values if term in value.casefold() and value not in exact]
    fuzzy = [
        value
        for value in get_close_matches(search_term, values, n=MAX_LOOKUP_RESULTS, cutoff=0.6)
        if value not in exact and value not in partial
    ]

    matches = (exact + partial + fuzzy)[:MAX_LOOKUP_RESULTS]

    return {
        "status": "success",
        "column": column,
        "search_term": search_term,
        "exact_match": exact[0] if exact else None,
        "matches": [{"value": value, "ticket_count": counts[value]} for value in matches],
        "note": (
            "No value matches this term. Tell the user instead of filtering on a guess."
            if not matches
            else "Filter with one of these values exactly as written."
        ),
    }


async def get_ticket(ticket_number: str, tool_context: ToolContext) -> SQLCommandResult:
    """Return every field of a single ticket.

    Args:
        ticket_number: Full ticket number, e.g. 'Z_INM200900A001'.
        tool_context: ADK tool context.

    Returns:
        SQLCommandResult with one row, or an empty result if the ticket does not exist.
    """

    layer = load_semantic_layer()
    columns = ", ".join(layer.queryable_columns)
    query = f"SELECT {columns} FROM {layer.dataset.table} WHERE ticket_number = :ticket_number LIMIT 1"

    try:
        with engine.connect() as connection:
            sql_command_logger.info(f"get_ticket: {ticket_number}")
            rows = json_safe_rows([
                dict(row)
                for row in connection.execute(
                    text(query), {"ticket_number": ticket_number.strip()}
                ).mappings().all()
            ])
    except SQLAlchemyError as error:
        logger.error(str(error))
        return SQLCommandResult.failure(str(error), sql_query=query)

    log_result_rows(f"get_ticket {ticket_number}", rows)
    return SQLCommandResult.success(rows=rows, sql_query=query)


def _build_filters(
    layer: SemanticLayer,
    metric: MetricSpec,
    supplied: dict[str, str],
) -> tuple[str, dict[str, Any], dict[str, str]]:
    """Translate the tool arguments into bound SQL predicates.

    Args:
        layer: The semantic layer.
        metric: The metric being executed.
        supplied: Raw filter arguments, empty values included.

    Returns:
        A tuple of (SQL fragment, bound parameters, filters actually applied).

    Raises:
        ValueError: If a filter or one of its values is not declared.
    """

    prefix = f"{metric.filter_alias}." if metric.filter_alias else ""
    clauses: list[str] = []
    params: dict[str, Any] = {}
    applied: dict[str, str] = {}

    for name, raw_value in supplied.items():
        value = str(raw_value).strip()
        if not value:
            continue

        spec = layer.filters.get(name)
        if spec is None:
            raise ValueError(f"Unknown filter '{name}'.")

        if spec.kind == "equals":
            clauses.append(f"AND {prefix}{spec.column} = :{name}")
            params[name] = value

        elif spec.kind == "group":
            members = layer.group_members(spec.group, value.lower())
            column = layer.groups[spec.group].column
            placeholders = [f":{name}_{index}" for index, _ in enumerate(members)]
            clauses.append(f"AND {prefix}{column} IN ({', '.join(placeholders)})")
            params.update(dict(zip([p[1:] for p in placeholders], members)))

        elif spec.kind == "prefix":
            patterns = layer.group_members(spec.group, value.upper())
            clauses.append(f"AND {prefix}{spec.column} LIKE :{name}")
            params[name] = patterns[0]

        elif spec.kind in ("date_from", "date_to"):
            try:
                datetime.strptime(value, DATE_INPUT_FORMAT)
            except ValueError as error:
                raise ValueError(f"'{name}' must use the format YYYY-MM-DD, got '{value}'.") from error
            operator = ">=" if spec.kind == "date_from" else "<"
            timestamp = f"STR_TO_DATE({prefix}{spec.column}, '{layer.dataset.timestamp_format}')"
            clauses.append(f"AND {timestamp} {operator} :{name}")
            params[name] = value

        applied[name] = value

    return "\n  ".join(clauses), params, applied


def build_metric_query(
    metric_name: str,
    supplied: dict[str, str],
    limit: int = 0,
    layer: SemanticLayer | None = None,
) -> tuple[str, dict[str, Any], dict[str, str]]:
    """Compose the parameterized statement of a metric.

    Separated from `run_metric` so the query can be built - and tested - without
    a database connection.

    Args:
        metric_name: Name of the metric in the catalogue.
        supplied: Filter arguments, empty values included.
        limit: Row limit. 0 uses the metric default.
        layer: Semantic layer override, only used in tests.

    Returns:
        A tuple of (SQL statement, bound parameters, filters actually applied).

    Raises:
        ValueError: If the metric, a filter or a filter value is not declared.
    """

    layer = layer or load_semantic_layer()

    metric = layer.metrics.get(metric_name)
    if metric is None:
        raise ValueError(
            f"Unknown metric '{metric_name}'. Available metrics: {', '.join(layer.metrics)}."
        )

    filters_sql, params, applied = _build_filters(layer, metric, supplied)

    row_limit = limit if limit > 0 else metric.default_limit
    params["row_limit"] = min(row_limit, settings.MAX_SQL_LIMIT)

    query = f"{metric.sql.format(filters=filters_sql).rstrip()}\nLIMIT :row_limit"
    return query, params, applied


async def run_metric(
    metric_name: str,
    tool_context: ToolContext,
    loc_identifier: str = "",
    network_element_identifier: str = "",
    subject: str = "",
    assignee_area: str = "",
    use_case: str = "",
    priority: str = "",
    status: str = "",
    status_group: str = "",
    ticket_type: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int = 0,
) -> SQLCommandResult:
    """Run a named metric from the catalogue with parameterized filters.

    Prefer this over writing SQL: the query is fixed, so the same question always
    returns the same answer. Call describe_schema('metrics') for the catalogue.
    Leave a filter empty to skip it.

    Args:
        metric_name: Name of the metric, e.g. 'top_resolutions'.
        tool_context: ADK tool context.
        loc_identifier: Site / location code, e.g. 'DZR1Y'.
        network_element_identifier: Network element id, e.g. 'OXVOWF7'.
        subject: Exact subject / alarm name, e.g. 'Link Down'.
        assignee_area: Team that owns the tickets.
        use_case: Business category of the ticket.
        priority: Priority 1-5.
        status: A single exact status value.
        status_group: 'active' or 'resolved'.
        ticket_type: 'INM', 'SRM', 'NEV', 'NBL' or 'PRM'.
        date_from: Inclusive start of the period, format YYYY-MM-DD.
        date_to: Exclusive end of the period, format YYYY-MM-DD.
        limit: Maximum number of rows. 0 uses the metric default.

    Returns:
        SQLCommandResult with the metric rows, the executed statement and the
        filters that were applied.
    """

    supplied = {
        "loc_identifier": loc_identifier,
        "network_element_identifier": network_element_identifier,
        "subject": subject,
        "assignee_area": assignee_area,
        "use_case": use_case,
        "priority": priority,
        "status": status,
        "status_group": status_group,
        "ticket_type": ticket_type,
        "date_from": date_from,
        "date_to": date_to,
    }

    try:
        query, params, applied = build_metric_query(metric_name, supplied, limit)
    except ValueError as error:
        return SQLCommandResult.failure(str(error))

    try:
        with engine.connect() as connection:
            sql_command_logger.info(f"run_metric '{metric_name}' filters={applied}: {query}")
            rows = json_safe_rows(
                [dict(row) for row in connection.execute(text(query), params).mappings().all()]
            )
    except SQLAlchemyError as error:
        logger.error(str(error))
        return SQLCommandResult.failure(str(error), sql_query=query)

    log_result_rows(f"run_metric {metric_name}", rows)

    if len(rows) > settings.MAX_ROWS:
        artifact = await save_rows_artifact(rows, tool_context, f"{metric_name}.json")
        return SQLCommandResult.success(
            rows=rows[: settings.MAX_ROWS],
            row_count=len(rows),
            truncated=True,
            artifact=artifact,
            sql_query=query,
        )

    return SQLCommandResult.success(rows=rows, sql_query=query)

"""Tools for the ticketing_master agent - reporting, charts, and Excel export."""

import io
import re
from datetime import datetime
from logging import getLogger
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from google.adk.tools import ToolContext
from google.genai.types import Part


logger = getLogger(__name__)

MAX_CELL_LENGTH = 80
MAX_CHART_CATEGORIES = 25
MAX_PIE_SLICES = 10
EXCEL_SHEET_NAME_LIMIT = 31
# Excel forbids these in a sheet name; the rest is filesystem hygiene.
_INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")
_INVALID_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def _markdown_cell(value: Any) -> str:
    """Render a value as a single, table-safe markdown cell."""

    if value is None:
        return "N/A"

    text = str(value).replace("|", "\\|").replace("\n", " ").strip()
    if len(text) > MAX_CELL_LENGTH:
        text = text[: MAX_CELL_LENGTH - 3] + "..."
    return text or "N/A"


def _safe_filename(filename: str, extension: str) -> str:
    """Turn a model-provided filename into a plain artifact name.

    The model chooses the name, so path separators and traversal segments are
    stripped before it is used as an artifact key.
    """

    stem = _INVALID_FILENAME_CHARS.sub("_", filename.strip().rsplit("/", 1)[-1].rsplit("\\", 1)[-1])
    stem = stem.removesuffix(extension).strip("._") or "export"
    return f"{stem}{extension}"


def _safe_sheet_name(sheet_name: str) -> str:
    """Clamp a worksheet name to what Excel accepts."""

    cleaned = _INVALID_SHEET_CHARS.sub("_", sheet_name).strip() or "Sheet1"
    return cleaned[:EXCEL_SHEET_NAME_LIMIT]


async def generate_report(
    title: str,
    summary: str,
    data: list[dict[str, Any]],
    columns: list[str],
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Generate a structured markdown report from query results.

    Args:
        title: Report title (e.g., 'Active Tickets with Link Down').
        summary: A brief executive summary of findings, including the filters applied.
        data: List of row dictionaries from the SQL query result.
        columns: Column names to include in the report table.
        tool_context: ADK tool context for artifact storage.

    Returns:
        A dictionary with the formatted report content.
    """

    if not data:
        return {"status": "success", "report": f"# {title}\n\n**No data found matching the criteria.**"}

    # build markdown report
    lines = []
    lines.append(f"# {title}")
    lines.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"\n## Summary\n{summary}")
    lines.append(f"\n**Total records:** {len(data)}")

    # Build table
    lines.append("\n## Details\n")
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    lines.append(header)
    lines.append(separator)

    for row in data:
        row_values = [_markdown_cell(row.get(col)) for col in columns]
        lines.append("| " + " | ".join(row_values) + " |")

    report_content = "\n".join(lines)

    # Save as artifact
    artifact_bytes = report_content.encode("utf-8")
    artifact = Part.from_bytes(data=artifact_bytes, mime_type="text/markdown")
    await tool_context.save_artifact("ticket_report.md", artifact)

    return {"status": "success", "report": report_content}


async def generate_chart(
    chart_type: str,
    title: str,
    data: list[dict[str, Any]],
    x_column: str,
    y_column: str,
    tool_context: ToolContext,
    x_label: str = "",
    y_label: str = "",
) -> dict[str, Any]:
    """Generate a chart image from query result data and save it as an artifact.

    Args:
        chart_type: Type of chart - 'bar', 'pie', 'line', or 'horizontal_bar'.
        title: Chart title.
        data: List of row dictionaries with the data to plot.
        x_column: Column name for the X axis (or labels for pie chart).
        y_column: Column name for the Y axis (or values for pie chart). Must be numeric.
        tool_context: ADK tool context for artifact storage.
        x_label: Optional X axis label.
        y_label: Optional Y axis label.

    Returns:
        A dictionary indicating success and the artifact filename.
    """

    if not data:
        return {"status": "failure", "error": "No data provided for chart generation."}

    df = pd.DataFrame(data)

    if x_column not in df.columns or y_column not in df.columns:
        return {
            "status": "failure",
            "error": f"Columns '{x_column}' or '{y_column}' not found in data. Available: {list(df.columns)}",
        }

    # Values arrive as Decimal or str depending on the driver; charts need numbers.
    df[y_column] = pd.to_numeric(df[y_column], errors="coerce")
    df = df.dropna(subset=[y_column])

    if df.empty:
        return {
            "status": "failure",
            "error": f"Column '{y_column}' holds no numeric values, so it cannot be plotted.",
        }

    max_categories = MAX_PIE_SLICES if chart_type == "pie" else MAX_CHART_CATEGORIES
    truncated = len(df) > max_categories
    if truncated:
        df = df.head(max_categories)

    fig, ax = plt.subplots(figsize=(10, 6))

    try:
        if chart_type == "bar":
            ax.bar(df[x_column].astype(str), df[y_column], color="steelblue")
            ax.set_xlabel(x_label or x_column)
            ax.set_ylabel(y_label or y_column)
            plt.xticks(rotation=45, ha="right")

        elif chart_type == "horizontal_bar":
            ax.barh(df[x_column].astype(str), df[y_column], color="steelblue")
            ax.set_xlabel(y_label or y_column)
            ax.set_ylabel(x_label or x_column)

        elif chart_type == "pie":
            if (df[y_column] < 0).any():
                return {"status": "failure", "error": "A pie chart needs non-negative values."}
            ax.pie(
                df[y_column],
                labels=df[x_column].astype(str),
                autopct="%1.1f%%",
                startangle=90,
            )
            ax.axis("equal")

        elif chart_type == "line":
            ax.plot(df[x_column].astype(str), df[y_column], marker="o", color="steelblue")
            ax.set_xlabel(x_label or x_column)
            ax.set_ylabel(y_label or y_column)
            plt.xticks(rotation=45, ha="right")

        else:
            return {
                "status": "failure",
                "error": f"Unsupported chart type: {chart_type}. Use 'bar', 'pie', 'line', or 'horizontal_bar'.",
            }

        ax.set_title(title)
        plt.tight_layout()

        # Save to buffer
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150)
        buf.seek(0)
    finally:
        plt.close(fig)

    artifact = Part.from_bytes(data=buf.read(), mime_type="image/png")
    artifact_name = "ticket_chart.png"
    await tool_context.save_artifact(artifact_name, artifact)

    return {
        "status": "success",
        "artifact": artifact_name,
        "plotted_rows": len(df),
        "message": (
            f"Chart '{title}' generated successfully."
            + (f" Only the first {max_categories} rows are shown." if truncated else "")
        ),
    }


async def export_to_excel(
    data: list[dict[str, Any]],
    columns: list[str],
    sheet_name: str,
    filename: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Export query results to an Excel file and save it as an artifact.

    Args:
        data: List of row dictionaries from the SQL query result.
        columns: Column names to include in the Excel file.
        sheet_name: Name for the Excel worksheet.
        filename: Desired filename for the Excel artifact (e.g., 'tickets_report.xlsx').
        tool_context: ADK tool context for artifact storage.

    Returns:
        A dictionary indicating success and the artifact filename.
    """

    if not data:
        return {"status": "failure", "error": "No data to export."}

    df = pd.DataFrame(data)

    # Filter to requested columns that exist
    available_cols = [c for c in columns if c in df.columns]
    if not available_cols:
        return {
            "status": "failure",
            "error": f"None of the requested columns found. Available: {list(df.columns)}",
        }

    df = df[available_cols]

    # Write to Excel buffer
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=_safe_sheet_name(sheet_name), index=False)
    buf.seek(0)

    artifact_name = _safe_filename(filename, ".xlsx")

    artifact = Part.from_bytes(
        data=buf.read(),
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    await tool_context.save_artifact(artifact_name, artifact)

    return {
        "status": "success",
        "artifact": artifact_name,
        "message": f"Excel file '{artifact_name}' exported with {len(df)} rows and columns: {available_cols}.",
    }

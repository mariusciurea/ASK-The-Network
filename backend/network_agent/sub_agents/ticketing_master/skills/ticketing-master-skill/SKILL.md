---
name: ticketing-master-skill
description: Analysis playbooks for network ticket reporting - which metric or query answers each recurring operations question, and how to present the result as a report, chart or Excel export.
---

# Ticketing Master Skill

## Overview
This skill holds the **methodology**: how to turn an operations question into the
right tool call and the right report.

It deliberately does **not** repeat the database schema. The schema, the filtering
rules and the metric catalogue live in `semantic_layer.yaml`; the core is always
present in the agent instruction and the details are available through
`describe_schema(topic)`. One source of truth, no drift.

---

## Tool order

1. `lookup_column_values(column, search_term)` - resolve the user's wording into a
   real value before it becomes a filter.
2. `run_metric(metric_name, ...)` - the catalogue answers most questions below,
   with SQL that is fixed and therefore reproducible.
3. `get_ticket(ticket_number)` - everything about one ticket.
4. `send_sql_command(sql_query)` - ad-hoc questions only. The query is validated
   against the semantic layer first; a rejection explains what to fix.
5. `generate_report` / `generate_chart` / `export_to_excel` - presentation.

---

## Playbooks

### 1. "How many tickets with the same problem in period X?"
`run_metric('ticket_volume_by_subject', date_from=..., date_to=...)`
Report + bar chart. Name the period explicitly in the summary.

### 2. "What were the root causes / how is this usually resolved?"
`run_metric('top_resolutions', subject=..., loc_identifier=...)`
Report + pie chart of the resolution distribution. `response_subject` is the
category; `response_description` is the engineer's own wording - quote it as an
example, never as a statistic.

### 3. "How many tickets with the same problem are active now, and where?"
`run_metric('active_clusters')`, optionally filtered by `subject`.
Report the clusters, the locations and the ticket numbers.

### 4. "What is the recurrence rate for alarm X on this hardware/site?"
`run_metric('recurrence_by_element', subject=..., network_element_identifier=...)`
Report occurrences, resolved count and the first/last occurrence. Recurrence is
a count over the dataset window - state the window.

### 5. "Are there change tickets active for this node?"
`run_metric('changes_on_element', network_element_identifier=..., status_group='active')`

### 6. "Which SLAs are about to expire?"
`run_metric('sla_at_risk', ticket_type='INM')`
`hours_to_deadline` is relative to the dataset reference date, not to today -
say so. Sort ascending, highlight negative values as already breached.

### 7. "Which issues were most frequent recently?"
`run_metric('ticket_volume_by_subject', date_from=...)` with the range anchored on
the dataset reference date. Report + horizontal bar chart for the top N.

### 8. "Can these incidents be correlated with recent changes?"
`run_metric('incidents_after_changes', network_element_identifier=...)`
This is a time-and-element correlation, **not** causality. Say that in the report.

### 9. "Distribution by priority / by region"
`run_metric('ticket_distribution_by_priority', ...)` or
`run_metric('ticket_volume_by_location', ...)`. Add percentages of the total.

### 10. "Put it in Excel"
Run the matching metric first, then `export_to_excel` with the same rows, and
also produce the report so the user sees the numbers in the chat.

### 11. "How long does it take to fix X?"
Not answerable: the dataset has no resolution timestamp. Say so and offer the
SLA-window statistics instead, clearly labelled as SLA target, not as MTTR.
See `describe_schema('limitations')`.

### 12. Ad-hoc questions
Write SQL only when no metric fits. Keep to the rules in the instruction:
structured columns for structured filters, `STR_TO_DATE` for dates,
`response_subject <> ''` for resolved tickets, always a LIMIT.

---

## Presentation strategy

| Question type | Tools |
|---------------|-------|
| Counts / volumes | metric -> `generate_report` + `generate_chart` (bar) |
| Distributions | metric -> `generate_report` + `generate_chart` (pie) |
| Trends over time | metric -> `generate_report` + `generate_chart` (line) |
| Top-N rankings | metric -> `generate_report` + `generate_chart` (horizontal_bar) |
| Lists / details | metric or SQL -> `generate_report` |
| Excel requests | metric or SQL -> `export_to_excel` + `generate_report` |
| SLA urgency | `sla_at_risk` -> `generate_report` sorted by deadline |

Every report states:
- the filters that were applied (column and value),
- the number of matching tickets,
- the time window and, for relative ranges, the anchor date,
- the ticket numbers behind the numbers, so the user can verify them.

---

## Honesty rules
- Never present a figure the query did not return.
- If a lookup returns no value for the user's term, say so and ask - do not
  substitute a similar-looking value.
- If the result set was truncated, say how many rows exist and point to the
  artifact holding the full set.
- Correlation is not causality; time proximity is not impact.

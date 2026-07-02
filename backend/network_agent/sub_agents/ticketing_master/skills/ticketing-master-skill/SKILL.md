---
name: ticketing-master-skill
description: Converts natural language requests into SQL queries, generates reports with visualizations, and exports data to Excel for network ticket analysis.
---

## Overview
The **ticketing_master** skill enables an agent to:
- Transform natural language questions into executable SQL queries
- Present results as structured professional reports
- Generate charts and graphs for visual analysis
- Export data to Excel when requested

This skill is designed for network operations reporting, including:
- Ticket volume and trend analysis
- Root cause and resolution analysis
- SLA compliance monitoring
- Recurrence and correlation analysis
- Change impact assessment
- MTTR (Mean Time To Resolution) calculations

---

## Tools

### `send_sql_command(sql_query: str)`
Executes a SQL query against the ticket database and returns row results.

### `generate_report(title: str, summary: str, data: list[dict], columns: list[str])`
Creates a formatted markdown report with title, executive summary, record count, and data table.
Use this for every query result to present findings professionally.

### `generate_chart(chart_type: str, title: str, data: list[dict], x_column: str, y_column: str, x_label: str, y_label: str)`
Generates a chart image from data. Chart types: `bar`, `horizontal_bar`, `pie`, `line`.
Use this when the data involves counts, distributions, trends, or comparisons.

### `export_to_excel(data: list[dict], columns: list[str], sheet_name: str, filename: str)`
Exports data to an .xlsx Excel file. Use when the user explicitly requests Excel/spreadsheet output.

---

## Database Schema

### Table: `ticket_data` (MySQL)

| Column | Type | Description |
|--------|------|-------------|
| ticket_number | VARCHAR(100) | Unique ticket ID. Prefix indicates type: INM=Incident, SRM=Service Request/Change, NEV=Network Event, NBL=Network Build, PRM=Problem |
| status | VARCHAR(50) | Ticket status: Open, In Progress, Assigned, Noticed, Closed, Answered |
| creator_area | VARCHAR(100) | Organizational area that created the ticket |
| use_case | VARCHAR(100) | Ticket category (e.g., Network-Incident, Change-Request) |
| subject | VARCHAR(255) | Short issue summary (e.g., "Link Down", "Störung - RBS - Huawei 4G") |
| priority | INTEGER | Priority level: 1 (critical) to 5 (low) |
| description | TEXT | Full incident description including alarm details |
| start | VARCHAR(50) | Incident/ticket start timestamp (format: 'M/D/YYYY H:MM') |
| sla_ticket | VARCHAR(50) | SLA deadline for INM tickets (format: 'M/D/YYYY H:MM') |
| network_element_identifier | VARCHAR(100) | Affected network element/node ID |
| loc_identifier | VARCHAR(100) | Site/location identifier (region code) |
| assignee_area | VARCHAR(100) | Team responsible for resolution |
| response_subject | VARCHAR(255) | Resolution category. Key values: "Behoben" (Fixed), "Root cause fixed", "Issue resolved", "No impact confirmed", "Kein Fehler - Ticket zurückgezogen" (No fault - ticket withdrawn) |
| response_description | TEXT | Detailed resolution description |

---

## Key Domain Knowledge

### Ticket Type Identification (by prefix)
- **INM** – Network Incidents (e.g., Z_INM200000A001)
- **SRM** – Service Requests / Changes
- **NEV** – Network Events
- **NBL** – Network Build activities
- **PRM** – Problems / Root Cause records

### Status Categories
- **Active:** Open, In Progress, Assigned, Noticed
- **Resolved:** Closed, Answered

### Resolution Categories (response_subject)
- "Behoben" = Fixed
- "Root cause fixed" = Root cause identified and resolved
- "Issue resolved" = Generic resolution
- "No impact confirmed" = False alarm / self-recovered
- "Kein Fehler - Ticket zurückgezogen" = No fault, ticket withdrawn
- "Monitoring ongoing" = Still under observation

### Date Handling (MySQL)
Dates are stored as strings. Use `STR_TO_DATE(column, '%m/%d/%Y %H:%i')` for date operations:
```sql
WHERE STR_TO_DATE(start, '%m/%d/%Y %H:%i') >= '2026-03-01'
  AND STR_TO_DATE(start, '%m/%d/%Y %H:%i') < '2026-04-01'
```

---

## Supported Query Patterns

### 1. Ticket Volume in Period
**Question:** "How many tickets with the same problem have been raised within X period?"
```sql
SELECT subject, COUNT(*) as ticket_count, 
       GROUP_CONCAT(ticket_number) as ticket_numbers
FROM ticket_data
WHERE STR_TO_DATE(start, '%m/%d/%Y %H:%i') >= '2026-03-01'
  AND STR_TO_DATE(start, '%m/%d/%Y %H:%i') < '2026-04-01'
GROUP BY subject
ORDER BY ticket_count DESC;
```
**Output:** Report + bar chart showing ticket counts by problem type.

### 2. Root Causes Identified
**Question:** "What were the root causes identified?"
```sql
SELECT response_subject, response_description, description,
       COUNT(*) as occurrence_count
FROM ticket_data
WHERE response_subject IS NOT NULL
  AND status IN ('Closed', 'Answered')
GROUP BY response_subject, response_description, description
ORDER BY occurrence_count DESC;
```
**Output:** Report with root cause categories and frequency.

### 3. Most Frequent Resolution for Alarm
**Question:** "Which was the most frequent resolution for a specific INM/alarm?"
```sql
SELECT response_subject, response_description, COUNT(*) as resolution_count
FROM ticket_data
WHERE description LIKE '%link down%'
  AND response_subject IS NOT NULL
GROUP BY response_subject, response_description
ORDER BY resolution_count DESC;
```
**Output:** Report + pie chart showing resolution distribution.

### 4. Active Tickets with Same Problem by Region
**Question:** "How many tickets with the same problem are active now? What regions are they from?"
```sql
SELECT subject, loc_identifier as region, 
       COUNT(*) as active_count,
       GROUP_CONCAT(ticket_number) as tickets
FROM ticket_data
WHERE status IN ('Open', 'In Progress', 'Assigned', 'Noticed')
GROUP BY subject, loc_identifier
HAVING active_count > 1
ORDER BY active_count DESC;
```
**Output:** Report showing clusters of active issues by region.

### 5. Recurrence Rate for Alarm on Specific HW/Site
**Question:** "What is the recurrence rate for alarm X on a specific HW/site?"
```sql
SELECT network_element_identifier, subject, 
       COUNT(*) as total_occurrences,
       SUM(CASE WHEN status = 'Closed' THEN 1 ELSE 0 END) as closed_count
FROM ticket_data
WHERE network_element_identifier = 'OXV5X0Q'
  AND description LIKE '%link down%'
GROUP BY network_element_identifier, subject;
```
**Output:** Report with recurrence statistics.

### 6. Active Change Tickets for Node
**Question:** "Are there any change tickets active for the node/nodes raised in this INM?"
```sql
SELECT ticket_number, subject, status, network_element_identifier, start
FROM ticket_data
WHERE network_element_identifier IN ('OXV5X0Q', 'OXVLAZK')
  AND (ticket_number LIKE 'Z_SRM%' OR ticket_number LIKE 'Z_NEV%' 
      OR ticket_number LIKE 'Z_NBL%' OR ticket_number LIKE 'Z_PRM%')
  AND status IN ('Open', 'In Progress', 'Assigned', 'Noticed');
```
**Output:** Report listing change tickets.

### 7. Multiple Tickets with Same Problem (Excel Export)
**Question:** "Do we have multiple tickets with the same problem/alarm? Put them in Excel."
```sql
SELECT subject as alarm, COUNT(*) as ticket_count, 
       GROUP_CONCAT(DISTINCT description SEPARATOR ' | ') as descriptions
FROM ticket_data
WHERE status IN ('Open', 'In Progress', 'Assigned', 'Noticed')
GROUP BY subject
HAVING ticket_count > 1
ORDER BY ticket_count DESC;
```
**Output:** Excel file with columns: alarm, ticket_count, description.

### 8. SLA Expiration Check
**Question:** "List tickets for which the SLA is due to expire."
```sql
SELECT ticket_number, subject, sla_ticket, status, priority
FROM ticket_data
WHERE status IN ('Open', 'In Progress', 'Assigned', 'Noticed')
  AND sla_ticket IS NOT NULL
  AND STR_TO_DATE(sla_ticket, '%m/%d/%Y %H:%i') <= NOW() + INTERVAL 4 HOUR
ORDER BY STR_TO_DATE(sla_ticket, '%m/%d/%Y %H:%i') ASC;
```
**Output:** Urgent report highlighting near-SLA tickets sorted by urgency.

### 9. Most Encountered Issues in Period
**Question:** "Which were the most encountered issues in the last <period>?"
```sql
SELECT subject, COUNT(*) as issue_count, 
       MIN(start) as first_occurrence, MAX(start) as last_occurrence
FROM ticket_data
WHERE STR_TO_DATE(start, '%m/%d/%Y %H:%i') >= NOW() - INTERVAL 30 DAY
GROUP BY subject
ORDER BY issue_count DESC
LIMIT 10;
```
**Output:** Report + bar chart with top issues.

### 10. INM Correlation with Recent Changes
**Question:** "Are there INM tickets that can be correlated with recent changes?"
```sql
SELECT inm.ticket_number as incident_ticket, 
       inm.description as incident_desc,
       inm.network_element_identifier,
       inm.start as incident_start,
       chg.ticket_number as change_ticket,
       chg.subject as change_subject,
       chg.start as change_start
FROM ticket_data inm
JOIN ticket_data chg 
  ON inm.network_element_identifier = chg.network_element_identifier
WHERE inm.ticket_number LIKE 'Z_INM%'
  AND (chg.ticket_number LIKE 'Z_SRM%' OR chg.ticket_number LIKE 'Z_NEV%' OR chg.ticket_number LIKE 'Z_NBL%')
  AND STR_TO_DATE(inm.start, '%m/%d/%Y %H:%i') >= STR_TO_DATE(chg.start, '%m/%d/%Y %H:%i')
  AND STR_TO_DATE(inm.start, '%m/%d/%Y %H:%i') <= STR_TO_DATE(chg.start, '%m/%d/%Y %H:%i') + INTERVAL 7 DAY
ORDER BY inm.start DESC;
```
**Output:** Report showing correlated incidents and changes.

### 11. Changes on Site in Period
**Question:** "What changes were made on this site in this period?"
```sql
SELECT ticket_number, subject, description, start,
       network_element_identifier, status
FROM ticket_data
WHERE network_element_identifier = 'OXV5X0Q'
  AND (ticket_number LIKE 'Z_SRM%' OR ticket_number LIKE 'Z_NEV%' OR ticket_number LIKE 'Z_NBL%')
  AND STR_TO_DATE(start, '%m/%d/%Y %H:%i') >= '2026-03-01'
  AND STR_TO_DATE(start, '%m/%d/%Y %H:%i') < '2026-04-01'
ORDER BY start;
```
**Output:** Report with chronological list of changes.

### 12. Average Solving Time (MTTR)
**Question:** "What is the average solving time for a specific alarm/ticket?"
```sql
SELECT subject,
       COUNT(*) as resolved_count,
       ROUND(AVG(TIMESTAMPDIFF(HOUR, 
           STR_TO_DATE(start, '%m/%d/%Y %H:%i'), 
           STR_TO_DATE(sla_ticket, '%m/%d/%Y %H:%i'))), 1) as avg_sla_hours,
       response_subject, response_description
FROM ticket_data
WHERE status IN ('Closed', 'Answered')
  AND response_subject IN ('Behoben', 'Root cause fixed', 'Issue resolved')
  AND description LIKE '%link down%'
GROUP BY subject, response_subject, response_description;
```
**Output:** Report with MTTR statistics (based on start-to-SLA window and resolution status).

### 13. Change Impact Analysis
**Question:** "Are there tickets that can be raised because of this change?"
```sql
SELECT ticket_number, description, subject, network_element_identifier, start
FROM ticket_data
WHERE ticket_number LIKE 'Z_INM%'
  AND network_element_identifier IN (
    SELECT network_element_identifier FROM ticket_data 
    WHERE ticket_number = 'Z_SRM_TARGET_TICKET'
  )
ORDER BY start DESC
LIMIT 20;
```
**Output:** Report showing historical incidents on same network elements.

### 14. Ticket Distribution by Priority (Excel Export)
**Question:** "Put in Excel the tickets distribution by priority within period X."
```sql
SELECT priority, COUNT(*) as ticket_count,
       GROUP_CONCAT(ticket_number) as tickets
FROM ticket_data
WHERE STR_TO_DATE(start, '%m/%d/%Y %H:%i') >= '2026-03-01'
  AND STR_TO_DATE(start, '%m/%d/%Y %H:%i') < '2026-04-01'
GROUP BY priority
ORDER BY priority;
```
**Output:** Excel file + bar chart showing distribution by priority.

---

## Report Output Strategy

| Question Type | Tools to Use |
|--------------|-------------|
| Counts / volumes | `send_sql_command` → `generate_report` + `generate_chart` (bar) |
| Distributions | `send_sql_command` → `generate_report` + `generate_chart` (pie) |
| Trends over time | `send_sql_command` → `generate_report` + `generate_chart` (line) |
| Top-N rankings | `send_sql_command` → `generate_report` + `generate_chart` (horizontal_bar) |
| Lists / details | `send_sql_command` → `generate_report` |
| Excel requests | `send_sql_command` → `export_to_excel` + `generate_report` |
| MTTR / averages | `send_sql_command` → `generate_report` |
| SLA urgency | `send_sql_command` → `generate_report` (sorted by deadline) |

---

## End-to-End Execution Flow
1. Parse the user request to identify intent, time ranges, filters, and desired output format.
2. Map intent to the `ticket_data` schema and generate appropriate SQL (MySQL dialect).
3. Validate SQL for safety (SELECT only, no destructive operations).
4. Execute with `send_sql_command(sql_query)`.
5. Analyze results and compute derived metrics if needed (e.g., percentages, rates).
6. Call `generate_report(...)` with a meaningful title and executive summary.
7. If visualization adds value, call `generate_chart(...)` with appropriate chart type.
8. If user requests Excel, call `export_to_excel(...)`.
9. Return the report content as the final response.

---

## Safety Rules
- Only generate SELECT queries (no DROP, DELETE, TRUNCATE, UPDATE, INSERT)
- Use parameterized-style patterns (avoid direct string concatenation of user input)
- Limit result sets with LIMIT when full scans are not needed
- Validate column names against the known schema before generating SQL


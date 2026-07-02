---
name: ticketing-master-skill
description: Converts natural language requests specific to tickets into SQL queries for database interactions.
---

## Overview
The **ticketing_master** skill enables an agent to transform user-provided natural language questions or instructions related to tickets into executable SQL queries.  
It is responsible for understanding intent, mapping it to the database schema, generating safe and valid SQL, and optionally executing the query via the provided tool.

This skill is especially useful for:
- Ticket data exploration
- Ad-hoc queries on tickets data

---

## Tools
* `send_sql_command(sql_query: str)`  
  Sends the SQL query to the database and returns the result.

---

## Database Schema
The current schema exposed to this skill includes the table below.

### Table: `ticket_data`

Table schema

Columns:
- ticket_number (string, primary key): Unique ticket ID
- status (string): Ticket status (Closed, Open, In Progress)
- creator_area (string): Area that created the ticket
- use_case (string): Type of incident (e.g., Network-Incident)
- subject (string): Issue summary (e.g., Huawei RBS, Link Down)
- priority (integer): Priority from 1 (critical) to 5 (low)
- description (text): Initial alert and incident description. here is described the fault
- start_time (timestamp): Incident start time
- sla_deadline (timestamp): SLA resolution deadline
- network_element_id (string): Affected network element
- location_id (string): Site/location identifier
- assignee_area (string): Responsible team
- response_subject (string): Resolution category
- response_description (text): Final resolution details


### Example query patterns
```sql
SELECT ticket_number, response_subject, response_description
FROM ticket_data
WHERE "transport issues" IN response_description;
```

---

## Responsibilities
The `ticketing_master` agent using this skill must:

1. **Understand user intent**
   - Parse the natural language input
   - Identify entities (tables, columns, filters, aggregations) based on attached database schema
   - Infer relationships if needed

2. **Generate valid SQL**
   - Construct syntactically correct SQL queries
   - Ensure compatibility with the target database dialect (if known)

3. **Ensure safety**
   - Avoid destructive operations (e.g., `DROP`, `DELETE`, `TRUNCATE`, `UPDATE`) unless explicitly required and allowed
   - Prefer read-only queries (`SELECT`)
   - Prevent SQL injection risks by not blindly trusting input

4. **Optimize queries**
   - Use appropriate filters (`WHERE`)
   - Limit results when necessary (`LIMIT`)
   - Avoid unnecessary joins or subqueries

5. **Execute queries when appropriate**
   - Use `send_sql_command` to run the query
   - Return results in a clear and structured format
   - By default, after generating the SQL, execute it and return the data (unless the user explicitly asks for SQL-only output)

---

## End-to-End Execution Flow
1. Parse the user request in natural language.
2. Map intent to the `ticket_data` schema and generate SQL.
3. Validate the SQL for safety and correctness.
4. Call `send_sql_command(sql_query)`.
5. Return the tool output to the user as the final answer (rows, empty result, or execution error).

---

## Output Format

### When generating SQL only:
```sql
SELECT column1, column2
FROM table_name
WHERE condition
LIMIT 100;
```

### When executing and returning data (default):
1. Generated SQL query
2. Tool call: `send_sql_command(sql_query)`
3. Final response with returned data in a concise, readable table or list


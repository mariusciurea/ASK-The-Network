---
name: ticketing-skill
description: Gathers information about tickets.
---

## Tools

There are MCP server tools available for retrieving ticket information:
* `get_tickets_info`  
  Retrieves information about tickets from the MCP server.
* `send_sql_command`  
  Sends the SQL query to the database and returns the result.
---

## Database Schema
If the user asks for information about tickets, the skill can access the 'test_ask_config' schema.

### Table: `ticket_data`

| Column                     | Type |
|----------------------------|------|
| Ticket Number              | text |
| Status                     | text |
| Creator Area               | text |
| Use Case                   | text |
| Subject                    | text |
| Priority                   | int  |
| Description                | text |
| Start                      | text |
| SLA Ticket                 | text |
| Network Element Identifier | text |
| Loc Identifier             | text |
| Assignee Area              | text |
| Response Subject           | text |
| Response Description       | text |




---
name: root-skill
description: Delegates tasks to sub-agents or agents-as-tools to handle network element configuration management across different platforms and vendors.
---

# Root Config Skill

## Overview
The **router-skill** is responsible for orchestrating network configuration activities by delegating tasks to specialized sub-agents. It acts as a central routing intelligence layer that determines the appropriate agent/tool to execute configuration, validation, or retrieval operations on network elements.
Use this skill when you need to delegate the tasks.
This skill does not perform direct database queries itself. Instead, it analyzes the request and delegates execution to the most suitable downstream agent.

---

## Responsibilities
- Interpret user or system requests related to network radio configuration
- Route tasks to the appropriate sub-agent or tool
- Normalize input parameters for downstream agents
- Aggregate and return responses from sub-agents
---

---

## Delegation Strategy
The skill determines which sub-agent to use based on:
- User intent and request parameters

---

## Sub-agents
- **RadioNetworkAgent**: Converts natural language requests into SQL queries for database interactions.
- **PlanningNetworkAgent**:If the user asks for free loopback IP addresses, always delegate the request to planning_agent.
- **TicketingAgent**:If the user asks for information about tickets, always delegate the request to ticketing_agent.

## Examples
**User**
- What is the 2G IP of network element Test?

**RootNetworkAgent**
- Based on the user prompt I need to delegate this task to RadioNetworkAgent (because Test is a radio network element and 2G IP is stored in the database)

**User**
- Give me 2 free loopback IP addresses in the subnet 10.0.0.0/24.

**RootNetworkAgent**
- Based on the user prompt I need to delegate this task to PlanningNetworkAgent (because it is responsible for generation free loopback IP addresses)

**User**
- Give me the most frequent issues handled in the tickets.

**RootNetworkAgent**
- Based on the user prompt I need to delegate this task to TicketingAgent (because it is responsible for gathering information about tickets)
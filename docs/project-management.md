# Project Management

This document keeps the decision-support project manageable in GitHub Issues and GitHub Projects without turning it into a heavy process.

## Live Board

- GitHub Project: https://github.com/users/vamos99/projects/2

## Workflow

Use a GitHub Projects board with these fields:

| Field | Values |
| --- | --- |
| Status | Backlog, Ready, In Progress, Review, Done |
| Priority | P0, P1, P2 |
| Area | analytics, dashboard, data-pipeline, spatial, docs, ci |
| Size | S, M, L |
| Sprint | Sprint 1, Sprint 2, Sprint 3 |

Recommended board columns:

1. Backlog: useful ideas, not yet scoped.
2. Ready: scoped tasks with acceptance criteria.
3. In Progress: one or two active tasks only.
4. Review: PR opened, checks passing or under review.
5. Done: merged or intentionally closed.

## Definition of Ready

- The issue states the decision or operational outcome.
- Input dataset, output table, and grain are named.
- Acceptance criteria include a reproducible command or query.
- Geospatial assumptions and data coverage risks are visible.

## Definition of Done

- Code or documentation is committed on a feature branch.
- Relevant compile, SQLite, or dashboard checks pass.
- Risk counts reconcile with `data/gold` or `outputs/chapter4`.
- README, runbook, or SQL docs are updated when behavior changes.
- PR summary includes what changed and how it was verified.

## Current Backlog

| Priority | Area | Task | Acceptance Criteria |
| --- | --- | --- | --- |
| P1 | analytics | Add metric dictionary for risk KPIs | PoF, CoF, risk score, and risk band definitions are documented. |
| P1 | spatial | Add map join quality table to dashboard | Matched, left-only, and right-only counts are visible for the latest run. |
| P1 | data-pipeline | Add SQLite view reconciliation check | View totals match `outputs/chapter4` city and district summaries. |
| P2 | dashboard | Add district drill-down summary | Selecting a district shows top neighborhoods and risk mix. |
| P2 | data-pipeline | Add freshness and completeness checks | Pipeline reports missing core input files and row-count changes. |
| P2 | docs | Add decision-support walkthrough | README explains how a non-technical reviewer should read the dashboard. |

## Sprint Plan

### Sprint 1 - Portfolio Baseline

- Executive risk dashboard
- SQLite analytics layer
- Lightweight CI

### Sprint 2 - Data Quality and Spatial Reliability

- Map join quality checks
- KPI dictionary
- Reconciliation queries

### Sprint 3 - Operational Decision Support

- District drill-down
- Freshness checks
- Scenario comparison notes

## Labels

- `type: task`, `type: bug`, `type: docs`
- `area: analytics`, `area: dashboard`, `area: data-pipeline`, `area: spatial`, `area: ci`
- `priority: P0`, `priority: P1`, `priority: P2`

## GitHub Projects Setup

Create a repository project named `ISKI Risk Prioritization Board`, add the fields above, then use the issue templates in `.github/ISSUE_TEMPLATE/` for new work.

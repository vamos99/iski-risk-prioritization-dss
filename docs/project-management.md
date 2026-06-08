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
| P2 | dashboard | Add district drill-down summary | Selecting a district shows top neighborhoods and risk mix. |
| P2 | docs | Add decision-support walkthrough | README explains how a non-technical reviewer should read the dashboard. |

## Recently Done

| Area | Task | Evidence |
| --- | --- | --- |
| analytics | Add metric dictionary for risk KPIs | `docs/metrics.md` |
| spatial | Add map join quality table to dashboard | `build_map_join_quality_table` and map tab table |
| data-pipeline | Add freshness and completeness checks | `scripts/validate_pipeline_outputs.py` |
| data-pipeline | Add SQLite view reconciliation check | `scripts/reconcile_analytics_sqlite.py` |

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

The project board already exists. Keep future issues small and link PRs back to
the board items when implementation starts.

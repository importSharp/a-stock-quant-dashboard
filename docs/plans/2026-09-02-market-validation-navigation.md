# Market Validation and Navigation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the dashboard into three clear workspaces and add a fail-closed market/data validation result that explains whether daily candidates are usable.

**Architecture:** A pure Python validator derives freshness, endpoint health, quote integrity, limit-price consistency, breadth, and break-rate checks from the current a-stock-data snapshot. The React dashboard replaces four overlapping tabs with three task-oriented workspaces and shows plain-language purpose, use, and decision impact for every section.

**Tech Stack:** Python 3.11 standard library, pytest, React 19, TypeScript, Vinext, responsive CSS.

---

### Task 1: Market validation contract

**Files:**
- Create: `scripts/market_validation.py`
- Create: `tests/test_market_validation.py`
- Modify: `scripts/a_stock_data_snapshot.py`

**Steps:**
1. Test green, yellow, red, stale-data, endpoint-error, and quote/limit inconsistency cases.
2. Implement deterministic checks with `now` passed explicitly.
3. Embed `marketValidation` before the daily-pick generation gate.
4. Make a red validation state prevent new 9:35 selections.

### Task 2: Three-workspace navigation

**Files:**
- Modify: `web/app/components/AStockDataDashboard.tsx`
- Modify: `web/app/globals.css`

**Steps:**
1. Replace 竞价/盘中/板块/候选 with 今日建议/市场验证/板块研究.
2. Keep the dual pool only under 今日建议.
3. Combine auction, indices, limit-up sentiment, and validation checks under 市场验证.
4. Combine board ranking, funds, breadth, and per-board candidates under 板块研究.

### Task 3: Explain every function

**Files:**
- Create: `web/app/components/FunctionGuide.tsx`
- Modify: `web/app/components/AStockDataDashboard.tsx`

**Steps:**
1. Add a compact “看什么 / 有什么用 / 如何影响建议” guide to each workspace.
2. Label raw data separately from custom rules.
3. Add explicit empty and degraded states.

### Task 4: Verification and delivery

**Files:**
- Modify: `README.md`
- Modify: `web/public/sw.js`

**Steps:**
1. Run all Python tests and the production frontend build.
2. Inspect all three tabs and the mobile viewport in the browser.
3. Bump the service-worker cache version, commit, and create an offline server bundle.

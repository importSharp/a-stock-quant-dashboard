# 9:35 Daily Picks Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a frozen 9:35 daily shortlist of up to three core and two watch candidates, each with explainable scores and reference price boundaries.

**Architecture:** A pure Python ranking module receives the existing a-stock-data snapshot plus opening-minute bars, applies time/source gates, scores and diversifies candidates, and persists the day's immutable selection. The snapshot publisher embeds the frozen result and refreshes only current prices/statuses; React renders one lead card and four compact cards.

**Tech Stack:** Python 3.11 standard library, React 19, TypeScript, Vinext, CSS, pytest, Node build verification.

---

### Task 1: Pure selection contract

**Files:**
- Create: `tests/test_daily_pick.py`
- Create: `scripts/daily_pick.py`

**Step 1:** Write failing tests for pre-9:35 `waiting`, the 9:35-9:40 generation window, post-window `no_pick`, source-health gates, main-board/ST/price filters, maximum five results, 3+2 tiers, and maximum two stocks per sector.

**Step 2:** Run `python -m pytest tests/test_daily_pick.py -q`; expect import/test failures.

**Step 3:** Implement typed helper functions for numeric coercion, code eligibility, candidate merging, score breakdown, diversification, and a serializable `dailyPick` contract. Accept `now` as an argument so tests are deterministic.

**Step 4:** Run the focused test file and confirm all selection-contract tests pass.

### Task 2: Opening price boundaries

**Files:**
- Modify: `tests/test_daily_pick.py`
- Modify: `scripts/daily_pick.py`
- Modify: `scripts/intraday_skill_analysis.py`

**Step 1:** Add failing tests for volume-weighted five-minute typical price, rounded reference range, breakout price, chase cap, invalidation, and missing-minute degradation.

**Step 2:** Add a Sina one-minute K-line reader using the existing standard-library HTTP helper. Limit minute requests to the pre-ranked shortlist.

**Step 3:** Implement deterministic price-band calculations bounded by the stock's limit-up price and opening range. Return explicit `priceSource` metadata.

**Step 4:** Run focused tests and confirm all boundary assertions pass.

### Task 3: Daily persistence and snapshot integration

**Files:**
- Modify: `scripts/a_stock_data_snapshot.py`
- Modify: `tests/test_daily_pick.py`

**Step 1:** Add failing tests that an existing same-day result is reused without reranking, an old-day file is ignored, and a failed generation cannot reuse yesterday's picks.

**Step 2:** Add atomic JSON persistence through a sibling temporary file followed by `Path.replace`. Store state under `data/runtime/daily-pick-YYYYMMDD.json`.

**Step 3:** Enrich candidate codes with Tencent quotes, request opening minutes only during the generation window, embed `dailyPick`, and update only `currentPrice` and `liveState` after freezing.

**Step 4:** Run `python -m pytest -q` and a one-shot snapshot command. Outside the window, verify the output is an honest waiting/closed state rather than a fabricated pick.

### Task 4: Decision-card frontend

**Files:**
- Create: `web/app/components/DailyPicks.tsx`
- Modify: `web/app/components/AStockDataDashboard.tsx`
- Modify: `web/app/globals.css`

**Step 1:** Extend the snapshot TypeScript contract and render a semantic empty/waiting/error state before adding success cards.

**Step 2:** Implement a lead-card plus four-card rail with tier, rank, score breakdown, sector, confirmation/current prices, reference range, breakout, chase cap, invalidation, live state, reasons, source and timestamp.

**Step 3:** Add responsive CSS matching the existing industrial trading-desk visual language. At widths below 760px, use a single-column layout with price levels in a two-column grid and no horizontal overflow.

**Step 4:** Keep the disclosure adjacent to the cards: research ranking, not probability or personalized buying advice.

### Task 5: Verification and delivery

**Files:**
- Modify: `README.md`
- Modify: `.gitignore`

**Step 1:** Document the 9:35 window, 3+2 limit, frozen behavior, state file, price meanings, and server restart implications. Ignore `*.bundle` artifacts.

**Step 2:** Run `python -m pytest -q`, `npm run build` in `web`, and a one-shot snapshot refresh.

**Step 3:** Start the local production server, inspect desktop and mobile widths, and verify success and empty-state layouts without overflow.

**Step 4:** Review the diff for secrets/generated data, commit the feature branch, merge it into `main`, push the private GitHub repository, and provide the Tencent server update/restart commands.

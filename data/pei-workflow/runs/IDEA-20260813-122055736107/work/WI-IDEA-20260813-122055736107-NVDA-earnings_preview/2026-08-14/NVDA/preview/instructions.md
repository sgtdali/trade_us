# Deterministic data pack -- read this before anything else

**This pack was built for `preview`.** `pack.json` says the same in
`intended_step`. If the two disagree, the pack is authoritative and the pack and
these instructions came from different runs -- stop and say so rather than
picking one.

Attached: `pack.json`. It contains one company, NVDA. It was prepared by my own pipeline from SEC XBRL
filings, a frozen price ledger and a dated analyst consensus snapshot.

It satisfies the `market_data_estimates` and `company_filings_ir` source
categories. Treat it as the user-named source and prefer it over web retrieval
for those categories.

## Deliverable surface

Markdown only -- no HTML report, dashboard, or screenshot pass.

## Source-of-truth rule

The numeric fields in `pack.json` are the **primary numeric source of truth**.

- Do **not** re-derive revenue, margins, growth, cash flow, multiples, market
  cap, consensus estimates, revisions or price targets from
  the web. They are already here, computed the same way for every company, so
  cross-company comparison is valid.
- Do **not** fill a missing value by estimating it. `unavailable` means
  unavailable and stays that way in your output.
- If something you find on the web contradicts a number in the pack, **say so
  explicitly** and name both values. Do not silently replace mine with theirs.

## Public sources, if you have them

If you have web search, it is worth using for what the pack does not contain:
news, events, management commentary, earnings call content, what the market is
currently debating, and sector or macro context. That layer is the one I cannot
produce.

## As-of dates -- these differ and it matters

| layer | as of |
|---|---|
| this pack was built on | 2026-08-14 |
| financial statement period end | 2026-04-26 |
| financial filing publication | 2026-05-20 |
| data eligibility cutoff | 2026-08-13T12:53:21.605685Z |
| latest market price and canonical valuation | 2026-08-13 |
| trailing returns / volatility / ADV | 2026-08-13 |
| analyst consensus | 2026-08-13 |

Quote the correct as-of when you cite a number. Anything after these dates
belongs to the web layer, not to the pack.

`valuation` is the canonical current valuation priced as of 2026-08-13.
`valuation_at_cutoff` preserves the original 2026-08-12 valuation snapshot.
For NVDA the two prices differ by +0.1%. Price-based multiples are updated by the exact price ratio.
Enterprise-value multiples are recomputed from refreshed market cap plus
filing-based net debt; any method that cannot be refreshed remains explicitly
listed in `price_refresh.not_rescaled` rather than silently mixed with current data.

## Names that reported after the cutoff -- read this before ranking

NVDA has not filed since the cutoff, so its financials here are the latest ones.

Affected companies carry `announced_but_not_filed` (filing dates, data age) --
some are a full quarter behind. This does not rescale away: source the newer
print and label it web-sourced, or say plainly the pack predates it. Do not
fold a newer headline number into a ratio built from older statements, and do
not rank a stale company against a current one without saying so.

## Corporate events -- three blocks, and what they are

Facts from the SEC filing index; what they mean for a company is yours to judge.

`special_situations` -- a completed acquisition, disposition, spin,
restatement, or amended 10-Q/10-K in the last two years (dates, 8-K item
numbers).

`fundamentals_comparability` -- present when such an event falls inside the
twelve months a company's growth rates span. Names the affected `*_growth`
fields: they compare periods covering different businesses, neither restated.
Single-period ratios are unaffected.

`transaction_filing_history` -- a 425, S-4 or merger proxy was found in the
filing window. Carries form mix, count, dates and a form-based role indicator
(merger proxy = soliciting its own shareholders; S-4 = registering securities;
425 alone = role unknown). **This does not establish that a transaction is
currently pending, completed or terminated. Deal terms, consideration,
counterparty, timetable, regulatory status and outcome are not in the pack.**

## What is deliberately NOT in the pack

Earnings call transcripts, expert-network work, options and implied-move data,
short interest and positioning, private-company transactions, and the terms of
any M&A deal. I have no source for these. Fill them from public sources if you
can and mark them as such; where you cannot, state the limitation and carry on.

## Mandate -- do not infer this, it is given

- **long only**, common equity only; no options, no leverage, no shorting.
- Universe: US listed. all sectors eligible; no exclusions.
- Review weekly, rebalance monthly. A weekly review or a monthly rebalance may change the portfolio but neither is obliged to. Holding through both is a valid outcome.
- Position count is not fixed. The screen decides how many names clear the bar. Note the consequence rather than working around it: fewer positions widen the band inside which luck alone explains the result.
- No liquidity floor. Measured on this universe 2026-08-09: the least liquid name trades USD 17m a day and the median USD 669m. A retail-sized position is well under a tenth of a percent of daily volume, so a liquidity screen would exclude nothing and only add a false constraint.
- No benchmark set yet. Do not assume one, and do not frame results as active weight against an index.

**Known tension, stated so you do not have to discover it:** The plugin's default fundamental horizon is 3-18 months while this mandate rebalances monthly. Measured in this repo: monthly decisions rest on data averaging 46 days old, and in 32% of company-months a new 10-Q or 10-K lands within 30 days of the decision. Filing-driven timing is the alternative; next_events carries the dates.

## Task

Use earnings-preview for NVDA.

I have no options or implied-move data and no positioning or short-interest
data. Do not construct an implied-move bar from an expiry that does not isolate
the event; say the input is missing instead.

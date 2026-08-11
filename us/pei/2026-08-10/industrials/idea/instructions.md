# Deterministic data pack -- read this before anything else

**This pack was built for `idea`.** `pack.json` says the same in
`intended_step`. If the two disagree, the pack is authoritative and the pack and
these instructions came from different runs -- stop and say so rather than
picking one.

Attached: `pack.json`. It contains 12 US large-cap companies, the whole of the industrials family and nothing else. Three other sector families are being run separately, so a bucket assigned here ranks a company against this pool rather than against the full universe. It was prepared by my own pipeline from SEC XBRL
filings, a frozen price ledger and a dated analyst consensus snapshot.

It satisfies the `market_data_estimates` and `company_filings_ir` source
categories. Treat it as the user-named source and prefer it over web retrieval
for those categories.

## Deliverable surface -- Markdown, not HTML

I am requesting Markdown as the presentation surface. Treat that as the
deliverable-intake answer and do not ask again.

No standalone HTML report, no dashboard, no `public_equity_investing_dashboard`
payload, no rendered artifact, and no headless-browser screenshot pass. Those
steps do not apply here and skipping them is not a reduction in scope.

Keep the full analytical depth the workflow calls for -- the same sections, the
same tables, the same evidence discipline -- just written as Markdown. Tables as
Markdown tables. If a chart would have carried the point, say it in a table or a
sentence instead.

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

To be clear about what is being asked: ordinary web search only. Nothing here
needs a browser to be driven, a page to be clicked through, or any
computer-control tool.

**If you have no web access, that is fine and not a reason to stop.** The pack
is self-contained. Do the analysis from it, and list what you would have checked
online as an open item.

## As-of dates -- these differ and it matters

| layer | as of |
|---|---|
| this pack was built on | 2026-08-10 |
| financial statements | 2026-08-07T23:59:59Z |
| prices / market cap, and every multiple | 2026-08-07 |
| analyst consensus | 2026-08-10 |

Quote the correct as-of when you cite a number. Anything after these dates
belongs to the web layer, not to the pack.

**Two prices, and they disagree.** Every multiple in `valuation` comes from the
price on 2026-08-07; the consensus block carries its own later price from
2026-08-10. `price_reconciliation` shows both and the gap. 0 of 12 names differ by 5% or more, the widest by 1%.

Quote the 2026-08-07 price beside any multiple you cite, and never mix the two
prices inside one comparison.

**Updating a multiple to the later price is exact, not an estimate.** Earnings,
book value and cash flow do not move in a few days; only the price does. So for
any price-based multiple:

    multiple_at_later_price = multiple x (consensus_block_price / multiples_computed_from)

and for a yield, divide instead of multiply. Both prices sit in
`price_reconciliation`. Do this when the later price matters to a conclusion,
show the arithmetic, and label the result with the later date. What you must not
do is rebuild a multiple from your own earnings figure.

The gap is not a defect in the numbers. The financials-to-price gap is
point-in-time discipline: decide on what was known at the cutoff, transact at
the next open. The price-to-consensus gap is a data lag on our side, and the
rescale above closes it.

## Names that reported after the cutoff -- read this before ranking

**2 of 12 names filed after 2026-08-07:** DE, PH.

For those names the financials here are not the latest ones. Some are a full
quarter behind: the pack holds Q1 while the company has already printed Q2.
Each affected company carries `announced_but_not_filed` with the filing dates
and the age of what we hold.

This one does not rescale away. Either source the newer print and label it as
web-sourced, or say plainly that the pack predates it. What you must not do is
drop a newer headline number into a ratio built from the older statements, or
rank a stale company against a current one without saying so.

## Corporate events -- three blocks, and what they are

These record facts from the SEC filing index. What they mean for a company is
yours to judge; I am not routing anything.

`special_situations` -- a completed acquisition, disposition or spin, a
restatement, or an amended 10-Q/10-K in the last two years, with dates and
8-K item numbers.

`fundamentals_comparability` -- present when such an event is dated inside the
twelve months a company's growth rates span. It names the affected `*_growth`
fields. Those fields put the current period beside a prior-year figure that
does not cover the same set of businesses, and neither period was restated
here. Single-period ratios compare nothing and are unaffected.

`pending_transaction` -- the company filed 425, S-4 or a merger proxy in the
window, and no completion filing appears. It carries the form mix, the count,
the dates, and which side of a transaction the forms place the company on: a
merger proxy solicits its own shareholders, an S-4 registers shares it would
issue, and 425 alone leaves the role unknown, which the block says. **Deal
terms, consideration, counterparty, timetable and regulatory status are not in
the pack.** Neither is the outcome; the filing count is a count.

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

Use idea-generation across all 12 companies in one screen.

Classify every ticker into your own bucket vocabulary -- `A - immediate research
candidate`, `B - watchlist / needs trigger`, `C - screen flag only`, `Reject` --
as research priority, not as a buy recommendation.

For each A name give Actionability, Variant Wedge, Why Now, First Rejection,
What Would Make It Investable, What Would Kill It, and Next Workflow.

End with a single table covering all 12 tickers, one row each:

| Ticker | Bucket | Setup | Variant wedge | First rejection | Next workflow |

Two companies reaching the same conclusion must still differ in their
company-specific evidence and first rejection. Repeated boilerplate rationale
is a failed run.

# Deterministic data pack -- read this before anything else

**This pack was built for `tearsheet`.** `pack.json` says the same in
`intended_step`. If the two disagree, the pack is authoritative and the pack and
these instructions came from different runs -- stop and say so rather than
picking one.

Attached: `pack.json`. It contains one company, NSC, plus its sector peer group. It was prepared by my own pipeline from SEC XBRL
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
2026-08-10. `price_reconciliation` shows both and the gap. For NSC the two prices differ by +0.0%.

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

NSC has not filed since the cutoff, so its financials here are the latest ones.

For those names the financials here are not the latest ones. Some are a full
quarter behind: the pack holds Q1 while the company has already printed Q2.
Each affected company carries `announced_but_not_filed` with the filing dates
and the age of what we hold.

This one does not rescale away. Either source the newer print and label it as
web-sourced, or say plainly that the pack predates it. What you must not do is
drop a newer headline number into a ratio built from the older statements, or
rank a stale company against a current one without saying so.

## Corporate events -- three blocks that outrank the ratios

Some companies are not a clean fundamentals case, and the ratios beside them
can be actively misleading. Read these three before ranking anything.

`special_situations` -- a completed acquisition, disposition or spin, a
restatement, or an amended 10-Q/10-K in the last two years.

`fundamentals_comparability` -- present when such an event landed inside the
twelve months the growth rates span. Every `*_growth` field for that company
then compares two different businesses. The percentages are arithmetically
correct and economically meaningless, and they can be enormous in either
direction. Do not read them as deterioration or improvement, and do not reject
or promote the company on them. The single-period ratios -- margins, current
ratio, leverage -- are unaffected, because they compare nothing.

`pending_transaction` -- the company is party to an announced merger or
acquisition that has not closed. Where it is the target, deal terms and the
odds of closing dominate its price; a weak quarter can be close to irrelevant.
This is an event-driven situation, not a fundamentals screen. **The pack holds
no deal terms, no consideration and no regulatory status** -- only the fact
that the filings exist and how many. Do not infer the outcome from the count,
and say plainly that the terms are not here.

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

Use company-tearsheet for NSC.

**Do not classify this name.** The tearsheet output contract ends at
`Recommended next step or downstream handoff`. Any add / trim / hold /
watchlist / wait-for-proof judgment belongs to earnings-preview,
long-short-pitch or thesis-tracker, not here. If you feel the need for a verdict
label, name the skill that owns it instead and stop.

What I want: the factual investor read, the core earnings-driver question, four
or five decision-useful metrics with period and source, valuation context,
concise catalysts and risks, material evidence gaps, and the next analytical
route.

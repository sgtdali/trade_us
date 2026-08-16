"""The read-only view.

Writing happens at the CLI; reading happens here, as a static file. There is no
server, no form, no session and no write path -- the page is a projection of
the ledger, regenerable at any time from the same data, and nothing about it
can change what the ledger says.

Self-contained by construction: styles are inline and there are no external
requests, so the file keeps working from a thumb drive in five years.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import instruments, sizing
from .decisions import issuer_weight_excluding
from .errors import FundError
from .money import format_display, to_decimal, to_string
from .projection import Valuation

STYLE = """
:root { --ink:#1a1d21; --muted:#6b7280; --rule:#e5e7eb; --warn:#8e2f2f;
        --ok:#256b62; --paper:#ffffff; --band:#f8f9fa; }
@media (prefers-color-scheme: dark) {
  :root { --ink:#e6e8ea; --muted:#9aa2ad; --rule:#2c3238; --warn:#e08a8a;
          --ok:#6fbfae; --paper:#15181b; --band:#1b1f23; }
}
* { box-sizing: border-box; }
body { margin:0; padding:2rem 1.25rem 4rem; background:var(--paper); color:var(--ink);
       font:15px/1.55 ui-sans-serif, -apple-system, "Segoe UI", system-ui, sans-serif; }
main { max-width: 62rem; margin: 0 auto; }
h1 { font-size:1.35rem; margin:0 0 .25rem; letter-spacing:-.01em; }
h2 { font-size:.8rem; text-transform:uppercase; letter-spacing:.09em;
     color:var(--muted); margin:2.5rem 0 .75rem; font-weight:600; }
.sub { color:var(--muted); margin:0 0 2rem; font-size:.9rem; }
.figures { display:flex; flex-wrap:wrap; gap:2.5rem; margin-bottom:.5rem; }
.figure .label { font-size:.72rem; text-transform:uppercase; letter-spacing:.08em;
                 color:var(--muted); }
.figure .value { font-size:1.5rem; font-variant-numeric:tabular-nums; }
.scroll { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums;
        font-size:.9rem; }
th { text-align:left; font-weight:600; font-size:.72rem; text-transform:uppercase;
     letter-spacing:.06em; color:var(--muted); padding:.4rem .6rem; white-space:nowrap;
     border-bottom:1px solid var(--rule); }
td { padding:.45rem .6rem; border-bottom:1px solid var(--rule); white-space:nowrap; }
tbody tr:nth-child(even) { background:var(--band); }
.num { text-align:right; }
.muted { color:var(--muted); }
.warn { color:var(--warn); }
.ok { color:var(--ok); }
ul.warnings { list-style:none; padding:0; margin:0; }
ul.warnings li { padding:.4rem .6rem; border-left:3px solid var(--warn); margin-bottom:.4rem;
                 background:var(--band); }
footer { margin-top:3rem; color:var(--muted); font-size:.8rem;
         border-top:1px solid var(--rule); padding-top:1rem; }
"""


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _pct(value: Decimal | None) -> str:
    return f"{value * 100:.2f}%" if value is not None else "&mdash;"


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]], numeric: Sequence[int] = ()) -> str:
    head = "".join(
        f'<th class="{"num" if index in numeric else ""}">{_e(header)}</th>'
        for index, header in enumerate(headers)
    )
    body = []
    for row in rows:
        cells = "".join(
            f'<td class="{"num" if index in numeric else ""}">{cell}</td>'
            for index, cell in enumerate(row)
        )
        body.append(f"<tr>{cells}</tr>")
    return (f'<div class="scroll"><table><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def build(
    *,
    policy: Mapping[str, Any],
    valuation: Valuation,
    master: Mapping[str, Any],
    assessments: Mapping[str, Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
    nav_history: Sequence[Mapping[str, str]],
    as_of: str,
) -> str:
    currency = valuation.base_currency
    warnings: list[str] = list(valuation.warnings)

    if valuation.nav is None:
        raise FundError("the report needs a NAV; supply the missing prices")

    peak = max((to_decimal(row["nav"]) for row in nav_history), default=valuation.nav.amount)
    drawdown = ((valuation.nav.amount - peak) / peak) if peak > 0 else Decimal(0)
    ladder = sizing.drawdown_response(policy, drawdown)

    rows: list[list[str]] = []
    for position in sorted(valuation.positions, key=lambda p: -(p.weight or Decimal(0))):
        ticker = instruments.ticker_for(dict(master), position.security_id)
        assessment = assessments.get(position.security_id)

        ceiling_text, status = "&mdash;", '<span class="muted">no assessment</span>'
        if assessment is None:
            warnings.append(f"{ticker} is held with no assessment on file")
        else:
            downside = assessment["downside"]
            try:
                result = sizing.evaluate(
                    policy,
                    readiness=assessment["readiness"],
                    downside_status=downside["status"],
                    downside_return_fraction=(to_decimal(downside["return_fraction"])
                                              if downside["status"] == "known" else None),
                    exposure=sizing.Exposure(
                        nav=valuation.nav.amount,
                        cash=valuation.cash.amount,
                        current_weight=position.weight or Decimal(0),
                        issuer_weight_excluding_security=issuer_weight_excluding(
                            valuation, master, position.security_id),
                    ),
                )
                ceiling_text = _pct(result.policy_compliant_max_weight)
                if (position.weight or Decimal(0)) > result.policy_compliant_max_weight:
                    status = '<span class="warn">over ceiling</span>'
                    warnings.append(
                        f"{ticker}: weight {_pct(position.weight)} exceeds its policy ceiling "
                        f"{ceiling_text} ({result.binding_constraint})"
                    )
                elif assessment["review_due"] < as_of:
                    status = '<span class="warn">review due</span>'
                    warnings.append(f"{ticker}: review was due {assessment['review_due']}")
                else:
                    status = '<span class="ok">ok</span>'
            except FundError:
                status = '<span class="warn">not sizable</span>'

        downside_text = "&mdash;"
        readiness = "&mdash;"
        review_due = "&mdash;"
        if assessment is not None:
            readiness = _e(assessment["readiness"])
            review_due = _e(assessment["review_due"])
            downside = assessment["downside"]
            downside_text = (_pct(to_decimal(downside["return_fraction"]))
                             if downside["status"] == "known" else '<span class="muted">unknown</span>')

        unrealized = (format_display(position.unrealized_pnl.amount)
                      if position.unrealized_pnl is not None
                      else f'<span class="muted">{_e(position.unrealized_unavailable_reason)}</span>')

        rows.append([
            _e(ticker),
            to_string(position.quantity),
            format_display(position.price.amount) if position.price else "&mdash;",
            format_display(position.market_value.amount) if position.market_value else "&mdash;",
            _pct(position.weight),
            ceiling_text,
            readiness,
            downside_text,
            unrealized,
            review_due,
            status,
        ])

    decision_rows = [
        [
            _e(record["as_of"]),
            _e(instruments.ticker_for(dict(master), record["security_id"])),
            _e(record["action"]),
            _e(record["outcome"]["decision"].replace("_", " ")),
            _e(record["policy_evaluation"]["binding_constraint"].replace("_", " ")),
            _e(record["mode"]),
        ]
        for record in list(decisions)[-15:][::-1]
    ]

    provisional = len(policy.get("provisional_fields", []))
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    parts = [
        "<style>", STYLE, "</style>",
        "<main>",
        f"<h1>Portfolio &mdash; {_e(as_of)}</h1>",
        f'<p class="sub">Read-only projection of the ledger. '
        f'Capital policy {_e(policy["identity"]["policy_version"])}, '
        f'{provisional} field(s) provisional.</p>',

        '<div class="figures">',
        f'<div class="figure"><div class="label">NAV</div>'
        f'<div class="value">{format_display(valuation.nav.amount)} {_e(currency)}</div></div>',
        f'<div class="figure"><div class="label">Cash</div>'
        f'<div class="value">{format_display(valuation.cash.amount)}</div>'
        f'<div class="muted">{_pct(valuation.cash_weight)} of NAV</div></div>',
        f'<div class="figure"><div class="label">Positions</div>'
        f'<div class="value">{len(valuation.positions)}'
        f'<span class="muted"> / {policy["capacity"]["max_active_positions"]}</span></div></div>',
        f'<div class="figure"><div class="label">Drawdown</div>'
        f'<div class="value">{_pct(drawdown)}</div>'
        f'<div class="muted">'
        + (f"peak {format_display(peak)} &middot; {ladder.replace('_', ' ')}" if ladder
           else f"peak {format_display(peak)} since {_e(nav_history[0]['as_of'])}"
           if nav_history else "no history yet")
        + "</div></div>",
        "</div>",

        "<h2>Positions</h2>",
        _table(
            ["Ticker", "Quantity", "Price", "Value", "Weight", "Ceiling", "Readiness",
             "Downside", "Unrealized", "Review due", "Status"],
            rows,
            numeric=(1, 2, 3, 4, 5, 7, 8),
        ) if rows else '<p class="muted">No open positions.</p>',
    ]

    if warnings:
        parts.append("<h2>Attention</h2>")
        parts.append('<ul class="warnings">')
        parts.extend(f"<li>{_e(warning)}</li>" for warning in dict.fromkeys(warnings))
        parts.append("</ul>")

    parts.append("<h2>Recent decisions</h2>")
    parts.append(
        _table(["As of", "Ticker", "Action", "Outcome", "Binding constraint", "Mode"], decision_rows)
        if decision_rows else '<p class="muted">No decisions recorded yet.</p>'
    )

    parts.append(
        f"<footer>Generated {generated} from the ledger. This page has no write path: "
        f"regenerate it with <code>fund report</code> after any change.</footer>"
    )
    parts.append("</main>")
    return "\n".join(parts)


def write(destination: Path, content: str) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    page = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>Portfolio</title>\n</head>\n<body>\n" + content + "\n</body>\n</html>\n"
    )
    destination.write_text(page, encoding="utf-8")
    return destination

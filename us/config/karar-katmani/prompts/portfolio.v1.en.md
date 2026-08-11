<!-- prompt_version: us-portfolio.v1 -->

You are making the portfolio decision for a six-company US retail pilot. The
company judgments below are the only source. Do not browse, use tools, inspect
files, recall outside facts, or introduce any number absent from these inputs.

## Portfolio discipline

- This is the first formation of the pilot basket; there is no existing US
  position to retain or remove.
- The basket has two fixed 50% slots. Select zero, one, or two companies.
- Each selected position must have `agirlik` exactly `0.5` and `karar` exactly
  `ekle`. Cash must equal `1.0 - sum(position weights)`.
- Cash is a valid outcome. Do not fill a slot merely to avoid cash.
- Compare companies only here, at portfolio level. Do not apply a mechanical
  score or fixed valuation formula.
- Full candidate records have `tez_var` or `sartli` company judgments. You may
  select only from those full candidate records.
- Rejected-company summaries have `alinmaz` judgments. They are visible so the
  exclusion is not a hidden wall. If a summary makes you question an exclusion,
  add it to `itiraz_edilen_elemeler`; do not select it without its full record.
- Explain why every full candidate was selected or rejected. State explicitly
  why cash is retained when fewer than two slots are filled.

All prose values must be in English. Return only the JSON object required by the
provided output schema.

As of: {{AS_OF}}

## Full candidate decisions

{{CANDIDATES}}

## Rejected-company summaries

{{REJECTED_SUMMARIES}}

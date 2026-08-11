"""Turkish-locale number and metric formatting for report rendering."""

from __future__ import annotations


def fmt_number(value: float | int | None, decimals: int = 1) -> str:
    if value is None:
        return "n/a"
    text = f"{value:,.{decimals}f}"
    integer_part, _, frac_part = text.partition(".")
    integer_part = integer_part.replace(",", ".")
    return f"{integer_part},{frac_part}" if decimals > 0 else integer_part


_UNIT_SUFFIX = {
    "percent": "%", "percentage_point": " puan", "ratio": "", "usc": " USc",
    "million_usd": " milyon USD", "million_try": " milyon TRY", "million": " milyon",
    "billion_km": " milyar km", "thousand_ton": " bin ton", "count": "", "usd_per_ton": " USD/ton",
    "us_cent": " USc",
}


def fmt_metric(metric: dict | None, decimals: int | None = None) -> str:
    if metric is None or metric.get("value") is None:
        return "veri yok"
    value = metric["value"]
    unit = metric.get("unit", "")
    places = decimals if decimals is not None else (2 if unit in ("percent", "ratio") else 1)
    number = fmt_number(value, places)
    if unit == "percent":
        return f"%{number}"
    suffix = _UNIT_SUFFIX.get(unit, f" {unit}")
    return f"{number}{suffix}"


def fmt_metric_comparison(metric: dict | None, decimals: int | None = None) -> str:
    """Same Turkish-locale/unit-suffix formatting as :func:`fmt_metric`, but
    for a metric's ``comparison_value`` instead of its ``value`` -- so a
    "current period / prior period" table renders both columns through the
    identical formatter rather than leaving the comparison column as a raw
    unformatted number."""
    if metric is None or metric.get("comparison_value") is None:
        return "veri yok"
    comparison_metric = {**metric, "value": metric["comparison_value"]}
    return fmt_metric(comparison_metric, decimals)


def fmt_change(metric: dict | None) -> str:
    if metric is None or metric.get("change") is None:
        return ""
    change = metric["change"]
    unit = metric.get("change_unit")
    sign = "+" if change > 0 else ""
    if unit == "percentage_point":
        return f"{sign}{fmt_number(change, 2)} yüzde puan"
    if unit == "ratio_points":
        return f"{sign}{fmt_number(change, 3)}"
    if unit == "percent":
        return f"{sign}{fmt_number(change, 1)}%"
    if unit == "currency_points":
        return f"{sign}{fmt_number(change, 1)} milyon USD"
    return str(change)

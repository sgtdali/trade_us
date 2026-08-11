"""Dedicated Markdown report for holding NAV/SOTP artifacts."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..reporting.semantic_catalog import label_for_metric


def _money(value: str | None, currency: str) -> str:
    if value is None:
        return "veri yok"
    number = Decimal(value)
    return f"{number:,.0f} {currency}".replace(",", ".")


def _percent(value: str | float | None) -> str:
    if value is None:
        return "veri yok"
    return f"%{Decimal(str(value)) * 100:.2f}".replace(".", ",")


def render_holding_report(
    assets: dict[str, Any],
    inputs: dict[str, Any],
    results: dict[str, Any],
    *,
    company_name: str,
    operational_summary: dict[str, Any] | None = None,
) -> str:
    """Render facts and blockers without industrial-company method leakage."""
    currency = results["reporting_currency"]
    lines = [
        f"# Holding NAD/SOTP Raporu: {company_name} ({results['ticker']})",
        "",
        "## 1. Kapsam ve yöntem",
        "",
        (
            f"Bu rapor {results['as_of_date']} tarihi itibarıyla iştirak ve varlıkları "
            "holdinglere özgü NAD/SOTP yaklaşımıyla inceler. Yalnız doğrulanabilir mevcut "
            "verileri sunar; ileriye dönük tahmin veya yatırım tavsiyesi üretmez."
        ),
        "",
        "## 2. Varlık ve iştirak envanteri",
        "",
        "| Varlık | Sahiplik | Değerleme esası | Brüt değer | Holding payına düşen | Durum |",
        "|---|---:|---|---:|---:|---|",
    ]
    by_id = {item["economic_asset_id"]: item for item in assets["assets"]}
    basis_labels = {
        "listed_market_value": "Aynı tarihli piyasa değeri",
        "disclosed_value": "Son 12 ayda açıklanan değer",
        "book_value": "Defter değeri",
        "unavailable": "Çözülemedi",
        "included_in_parent": "Üst varlık içinde",
    }
    for row in results["asset_rows"]:
        reasons = ", ".join(row["reason_codes"]) if row["reason_codes"] else "kullanılabilir"
        lines.append(
            f"| {row['name']} | {_percent(row['ownership_pct'])} | "
            f"{basis_labels[row['valuation_basis']]} | {_money(row['gross_value'], currency)} | "
            f"{_money(row['attributable_value'], currency)} | {reasons} |"
        )

    nav = results["nav_bridge"]
    lines.extend(
        [
            "",
            "## 3. NAD köprüsü",
            "",
            f"- Holding payına düşen çözülebilir varlık değeri: **{_money(nav['attributable_asset_value'], currency)}**",
            f"- Ana ortaklık solo nakit: **{_money(nav['parent_cash'], currency)}**",
            f"- Ana ortaklık solo finansal borç: **{_money(nav['parent_financial_debt'], currency)}**",
            f"- Ana ortaklık solo net nakit: **{_money(nav.get('parent_net_cash'), currency)}**",
            f"- Kanıtlanmış diğer düzeltmeler: **{_money(nav['other_adjustments'], currency)}**",
            f"- Toplam NAD: **{_money(nav['total_nav'], currency)}**",
            f"- Hisse başına NAD: **{_money(results['per_share_nav']['value'], 'TRY/pay')}**",
            f"- Gözlenen güncel iskonto/prim: **{_percent(results['observed_discount_premium']['value'])}**",
            "",
            "Konsolide borç NAD'dan düşülmemiştir; yalnız risk görünümü olarak sunulur.",
            f"Konsolide finansal borç: **{_money(inputs['consolidated_financial_position']['financial_debt'].get('value'), currency)}**.",
            "",
            "## 4. Kapsama ve engeller",
            "",
            f"- Çözülemeyen önemlilik oranı: **{_percent(inputs['coverage']['unresolved_ratio'])}**",
            f"- Kabul eşiği: **{_percent(inputs['materiality_threshold'])}**",
        ]
    )
    blockers = results["blocker_codes"]
    if blockers:
        lines.append("- Hesaplamayı sınırlayan nedenler:")
        lines.extend(f"  - `{code}`" for code in blockers)
    else:
        lines.append("- Hesaplamayı engelleyen açık veri boşluğu bulunmadı.")

    lines.extend(["", "## 5. Operasyonel görünüm", ""])
    if operational_summary:
        current = operational_summary["current_ebitda"]
        ttm = operational_summary["ttm_ebitda"]
        lines.extend(
            [
                (
                    f"- {label_for_metric('ebitda_amount')} ({current['period']}): "
                    f"**{_money(current['value'], currency)}**"
                ),
                (
                    f"- {label_for_metric('ebitda_ltm_amount')} ({ttm['period']}): "
                    f"**{_money(ttm['value'], currency)}**"
                ),
            ]
        )
        if ttm["status"] != "available":
            lines.append(
                "- TTM FAVÖK aynı tanım, para birimi ve satın alma gücü bazında kurulamadığı "
                "için tahmin edilmemiştir."
            )
    else:
        lines.append("- Holding için doğrulanmış FAVÖK katmanı bulunmuyor.")

    lines.extend(["", "## 6. Değerleme bazının bileşimi", ""])
    lines.extend(
        [
            f"- Halka açık iştirak piyasa değeri: {_money(results['valuation_basis_mix']['listed_market_value'], currency)}",
            f"- Son 12 ayda açıklanan değer: {_money(results['valuation_basis_mix']['disclosed_value'], currency)}",
            f"- Defter değeri: {_money(results['valuation_basis_mix']['book_value'], currency)}",
            "",
            "## 7. İddia–kaynak bağlantıları",
            "",
        ]
    )
    for row in results["asset_rows"]:
        source = by_id.get(row["economic_asset_id"], {}).get("evidence")
        if source:
            page = f", s. {source['page']}" if source.get("page") else ""
            lines.append(
                f"- **{row['name']}** — `{source['source_id']}` / `{source['source_file']}`{page}: "
                f"“{source['quoted_text']}”"
            )
    lines.extend(
        [
            "",
            "## 8. Sınırlar",
            "",
            "Eksik değerler sıfır kabul edilmemiştir. Ana ortaklık solo verisi yerine holding segmenti veya "
            "konsolide toplam kullanılmamıştır. Bir iştirak altında bulunan alt varlıklar ikinci kez NAD'a eklenmez.",
            "",
        ]
    )
    return "\n".join(lines)

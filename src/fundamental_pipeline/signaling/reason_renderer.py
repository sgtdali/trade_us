"""Localized reason rendering.

Evaluators return a machine-readable ``reason_code`` plus ``reason_params``;
this module turns that pair into a human-readable sentence. Templates are
kept here, not inside evaluator logic, so a new locale can be added without
touching signal rules.
"""

from __future__ import annotations


def _fmt(value):
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return str(value)


def _fmt_pct(value):
    """Format a ``*_pct`` reason param, including its own '%' sign.

    TR templates that combine two independently-optional percentages in one
    sentence (e.g. lease burden, deferred revenue) previously hardcoded a
    literal '%' immediately before the placeholder. When that value was
    ``None`` this rendered a bare "%-" with no indication the figure was
    missing. Returning the sign as part of the formatted value lets a
    missing side read as a real phrase instead.
    """
    if value is None:
        return "mevcut değil"
    if value < 0:
        return f"-%{_fmt(-value)}"
    elif value > 0:
        return f"+%{_fmt(value)}"
    return f"%{_fmt(value)}"


_TEMPLATES_TR = {
    "growth_positive": "Değer yıllık bazda {growth_pct} artmıştır (büyüme kuralı v1: ≥ %5 pozitif eşiğinin üzerinde).",
    "growth_negative": "Değer yıllık bazda {growth_pct} gerilemiştir (büyüme kuralı v1: ≤ -%5 negatif eşiğinin altında).",
    "growth_neutral": "Değer yıllık bazda {growth_pct} değişmiştir; büyüme kuralı v1 eşikleri (±%5) içinde yatay kabul edilir.",
    "growth_unavailable": "Karşılaştırma için gerekli değerler mevcut değil.",
    "loss_to_profit": "Karşılaştırma döneminde zarar ({previous}) varken bu dönem kâra ({current}) dönülmüştür.",
    "profit_to_loss": "Karşılaştırma döneminde kâr ({previous}) varken bu dönem zarara ({current}) dönülmüştür.",
    "loss_narrowing": "Zarar {previous}'den {current}'e daralmıştır ({narrowed_pct} daralma; zarar daralma kuralı v1: ≥ %20 daralma 'mixed').",
    "loss_narrowing_minor": "Zarar {previous}'den {current}'e sınırlı ölçüde daralmıştır ({narrowed_pct} daralma; zarar daralma kuralı v1 eşiğinin altında).",
    "loss_widening": "Zarar {previous}'den {current}'e büyümüştür.",
    "margin_positive": "Marj değişimi +{change_pp} yüzde puan ile pozitif eşiğin (≥ +0,5 puan) üzerindedir.",
    "margin_negative": "Marj değişimi {change_pp} yüzde puan ile negatif eşiğin (≤ -0,5 puan) altındadır.",
    "margin_neutral": "Marj değişimi {change_pp} yüzde puan ile yatay kabul edilir (±0,5 puan aralığında).",
    "margin_unavailable": "Marj karşılaştırması için gerekli değerler mevcut değil.",
    "cost_rising": "Birim maliyet yıllık bazda {growth_pct} artmıştır.",
    "cost_declining": "Birim maliyet yıllık bazda {growth_pct} gerilemiştir.",
    "cost_flat": "Birim maliyet yıllık bazda değişmemiştir.",
    "cost_unavailable": "Birim maliyet karşılaştırması için gerekli değerler mevcut değil.",
    "dual_growth_confirmed_positive": "Değer hem raporlanan bazda {reported_growth_pct} hem de kur etkisi hariç {constant_currency_growth_pct} artmıştır.",
    "dual_growth_confirmed_negative": "Değer hem raporlanan bazda {reported_growth_pct} hem de kur etkisi hariç {constant_currency_growth_pct} gerilemiştir.",
    "dual_growth_disagreement": "Raporlanan ({reported_growth_pct}) ve kur etkisi hariç ({constant_currency_growth_pct}) büyüme yönleri birbirini teyit etmemektedir.",
    "dual_growth_reported_only_positive": "Yalnızca raporlanan büyüme ({reported_growth_pct}) mevcuttur ve pozitiftir; kur etkisi hariç veri bulunmadığından sinyal bir kademe temkinli tutulmuştur.",
    "dual_growth_reported_only_negative": "Yalnızca raporlanan büyüme ({reported_growth_pct}) mevcuttur ve negatiftir; kur etkisi hariç veri bulunmadığından sinyal bir kademe temkinli tutulmuştur.",
    "dual_growth_reported_only_flat": "Yalnızca raporlanan büyüme ({reported_growth_pct}) mevcuttur ve yataydır.",
    "dual_growth_unavailable": "Büyüme karşılaştırması için gerekli değerler mevcut değil.",
    "cash_conversion_improved": "İşletme nakit akışı / net kâr oranı {change} oran puanı artmıştır.",
    "cash_conversion_deteriorated": "İşletme nakit akışı / net kâr oranı {change} oran puanı gerilemiştir.",
    "cash_conversion_flat": "İşletme nakit akışı / net kâr oranı büyük ölçüde yataydır.",
    "cash_conversion_unavailable": "İşletme nakit akışı / net kâr oranı hesaplanamamıştır.",
    "cash_conversion_no_comparison": "Karşılaştırma dönemi net kârı negatif veya hesaplanamaz olduğu için oranın yıllık değişimi anlamlı biçimde karşılaştırılamaz.",
    "liquidity_directional": "Cari oran değişimi ({current_ratio_change}) ve nakit+kısa vadeli yatırım oranı değişimi ({cash_ratio_change}) aynı yöndedir.",
    "liquidity_mixed": "Cari oran değişimi ({current_ratio_change}) ve nakit+kısa vadeli yatırım oranı değişimi ({cash_ratio_change}) farklı yönlerdedir.",
    "liquidity_unavailable": "Likidite karşılaştırması için gerekli değerler mevcut değil.",
    "leverage_directional": "Kaldıraç oranlarındaki ortalama değişim ({magnitude}) yönlü bir sinyal üretecek büyüklüktedir.",
    "leverage_flat": "Kaldıraç oranlarındaki değişim ({magnitude}) yatay kabul edilecek kadar küçüktür.",
    "leverage_mixed": "Kira dahil yükümlülük/özkaynak değişimi ({liability_ratio_change}) ve net borç/EBITDAR değişimi ({net_debt_ratio_change}) farklı yönlerdedir.",
    "leverage_unavailable": "Kaldıraç karşılaştırması için gerekli değerler mevcut değil.",
    "lease_burden_directional": "Kira yükümlülüğü büyümesi ({lease_liability_growth_pct}) ve kira ödemeleri büyümesi ({lease_payments_growth_pct}) birlikte değerlendirilmiştir.",
    "lease_burden_unavailable": "Kira yükü karşılaştırması için gerekli değerler mevcut değil.",
    "deferred_revenue_growing": "Ertelenmiş gelir bakiyesi ({balance_growth_pct}) ve nakit akışına katkısı ({cash_flow_growth_pct}) birlikte büyümüştür.",
    "deferred_revenue_shrinking": "Ertelenmiş gelir bakiyesi ({balance_growth_pct}) ve nakit akışına katkısı ({cash_flow_growth_pct}) birlikte gerilemiştir.",
    "deferred_revenue_mixed": "Ertelenmiş gelir bakiyesi ({balance_growth_pct}) ve nakit akışına katkısı ({cash_flow_growth_pct}) farklı yönlerdedir.",
    "deferred_revenue_unavailable": "Ertelenmiş gelir karşılaştırması için gerekli değerler mevcut değil.",
    "signal_context_raw_preserved": "Ham sinyal ek bir bağlam kısıtı olmadan sunulabilir.",
    "signal_context_unavailable": "Ham sinyal hesaplanamadığı için bağlamsal sınıflandırma yapılamamıştır.",
    "signal_context_improving_but_negative": "Gösterge iyileşmektedir ancak güncel seviyesi hâlâ negatiftir; koşulsuz olumlu olarak sunulmaz.",
    "signal_context_positive_limited_by_missing_data": "Olumlu yön kısmi veriden türetilmiştir; zorunlu bileşenler eksik olduğundan koşulsuz olumlu olarak sunulmaz.",
    "signal_context_negative_preserved_with_missing_data": "Zorunlu bileşenlerin bir bölümü eksiktir; gözlenen olumsuz yön ihtiyat gereği korunmuştur.",
}

_TEMPLATES_EN = {
    "growth_positive": "Value grew {growth_pct}% year over year (growth rule v1: above the +5% positive threshold).",
    "growth_negative": "Value declined {growth_pct}% year over year (growth rule v1: below the -5% negative threshold).",
    "growth_neutral": "Value changed {growth_pct}% year over year; within the +/-5% flat band of growth rule v1.",
    "growth_unavailable": "Required values for the comparison are unavailable.",
    "loss_to_profit": "The comparison period was a loss ({previous}); this period turned to a profit ({current}).",
    "profit_to_loss": "The comparison period was a profit ({previous}); this period turned to a loss ({current}).",
    "loss_narrowing": "The loss narrowed from {previous} to {current} ({narrowed_pct}% narrowing; loss-narrowing rule v1: >=20% narrowing is 'mixed').",
    "loss_narrowing_minor": "The loss narrowed only modestly from {previous} to {current} ({narrowed_pct}%; below the loss-narrowing rule v1 threshold).",
    "loss_widening": "The loss widened from {previous} to {current}.",
    "margin_positive": "Margin change of +{change_pp} percentage points is above the positive threshold (>=+0.5pp).",
    "margin_negative": "Margin change of {change_pp} percentage points is below the negative threshold (<=-0.5pp).",
    "margin_neutral": "Margin change of {change_pp} percentage points is treated as flat (within +/-0.5pp).",
    "signal_context_raw_preserved": "The raw signal may be presented without an additional context limitation.",
    "signal_context_unavailable": "The raw signal is unavailable, so no contextual classification can be made.",
    "signal_context_improving_but_negative": "The indicator is improving, but its current level remains negative; it is not presented as unconditionally positive.",
    "signal_context_positive_limited_by_missing_data": "The favorable direction is based on partial data; required components are missing, so it is not presented as unconditionally positive.",
    "signal_context_negative_preserved_with_missing_data": "Some required components are missing; the observed adverse direction is retained as a precaution.",
}


def render(locale: str, reason_code: str, params: dict) -> str:
    templates = _TEMPLATES_TR if locale.startswith("tr") else _TEMPLATES_EN
    template = templates.get(reason_code) or _TEMPLATES_TR.get(reason_code)
    if template is None:
        return f"{reason_code}: " + ", ".join(f"{k}={_fmt(v)}" for k, v in sorted(params.items()))
    is_tr = locale.startswith("tr")
    formatted = {k: (_fmt_pct(v) if is_tr and k.endswith("_pct") else _fmt(v)) for k, v in params.items()}
    try:
        return template.format(**formatted)
    except (KeyError, IndexError):
        return f"{reason_code}: " + ", ".join(f"{k}={_fmt(v)}" for k, v in sorted(params.items()))

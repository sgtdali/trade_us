from __future__ import annotations

from datetime import date
from pathlib import Path

from .errors import SecDataError
from .models import SecFact


_IXDS_READY = False


def _enable_document_set_plugin(controller) -> None:
    """Arelle'in inline belge kumesi eklentisini bir kez etkinlestirir."""
    global _IXDS_READY
    from arelle import PluginManager

    if _IXDS_READY:
        return
    PluginManager.init(controller, loadPluginConfig=False)
    PluginManager.loadModule(PluginManager.addPluginModule("inlineXbrlDocumentSet"))
    if not PluginManager.hasPluginWithHook("ModelDocument.PullLoader"):
        raise SecDataError("Arelle inlineXbrlDocumentSet plugin did not register its loader")
    _IXDS_READY = True


def load_facts(primary_document: Path | tuple[Path, ...]) -> tuple[SecFact, ...]:
    """Bir inline belgenin -- ya da bir inline belge KUMESININ -- fact'leri.

    Cok belgeli inline XBRL'de `ix:header` (ve dolayisiyla `schemaRef`) yalniz
    bir belgede bulunur; digerleri sadece `ix:nonFraction` tasir ve tek
    baslarina ayristirildiklarinda sifir fact verirler. CLX'in 2025 10-K'si
    boyle: birincil belge 68 fact, finansal tablolarin oldugu ikinci belge tek
    basina 0, kume olarak 1.998 (olculdu 2026-08-06). Arelle bunu ancak
    IXDS surrogate URI'siyle ve uyeler MUTLAK yol olarak verildiginde cozer --
    goreli isimler calisma dizinine gore aranir ve sessizce bos model doner.
    """
    try:
        from arelle import Cntlr, ModelManager
    except ImportError as exc:
        raise SecDataError("Arelle is required; install the project with the 'us' optional dependency") from exc

    documents = (primary_document,) if isinstance(primary_document, Path) else tuple(primary_document)
    if not documents:
        raise SecDataError("load_facts requires at least one document")

    controller = Cntlr.Cntlr()
    if len(documents) > 1:
        from arelle.UrlUtil import IXDS_DOC_SEPARATOR, IXDS_SURROGATE

        _enable_document_set_plugin(controller)
        members = [str(path.resolve()) for path in documents]
        target = (str(documents[0].resolve().parent / IXDS_SURROGATE)
                  + IXDS_DOC_SEPARATOR.join(members))
    else:
        target = str(documents[0].resolve())
    manager = ModelManager.initialize(controller)
    model = manager.load(target)
    try:
        if model is None or not model.facts:
            raise SecDataError(f"Arelle could not load XBRL facts from {primary_document}")
        result: list[SecFact] = []
        for fact in model.facts:
            context = fact.context
            if context is None or fact.qname is None or getattr(fact, "isTuple", False):
                continue
            end_date = getattr(context, "endDate", None)
            if not isinstance(end_date, date):
                continue
            start_datetime = getattr(context, "startDatetime", None)
            start_date = start_datetime.date() if start_datetime is not None else None
            dimensions = tuple(sorted(
                (dimension.clarkNotation, member.memberQname.clarkNotation if member.memberQname is not None else str(member.typedMember))
                for dimension, member in context.qnameDims.items()
            ))
            result.append(SecFact(
                namespace=fact.qname.namespaceURI,
                concept=fact.qname.localName,
                value=fact.value,
                unit=_canonical_unit(fact),
                context_id=fact.contextID,
                start_date=start_date,
                end_date=end_date,
                dimensions=dimensions,
                decimals=str(fact.decimals) if fact.decimals is not None else None,
                is_nil=bool(fact.isNil),
            ))
        return tuple(result)
    finally:
        model.close()
        controller.close()


def _canonical_unit(fact) -> str | None:
    """Return the XBRL measure, not the issuer-defined ``unitRef`` identifier."""
    unit = getattr(fact, "unit", None)
    measures = getattr(unit, "measures", None)
    if not measures or len(measures) != 2:
        return fact.unitID
    numerator, denominator = measures
    if len(numerator) != 1 or len(denominator) > 1:
        return fact.unitID
    numerator_name = numerator[0].localName
    if not denominator:
        return numerator_name
    return f"{numerator_name}/{denominator[0].localName}"

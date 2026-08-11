"""Canli koke KENDI gecmisini isle -- donmus backtest koklerine bagimliligi bitir.

Bugun uc yerde donmus kosulardan okuyoruz ve hepsi ayni sebepten:

  us_valuation_history.py   32 kesitlik carpan gecmisi
  us_pei_pack.py            ceyreklik seri (sirket basina 12 ceyrek)
  us_pei_csv.py             earnings-preview CSV'si

Canli kokte tek kesim var, o yuzden gecmis oradan geliyor. Bu betik canli koke
kendi aylik kesimlerini isler; sonra yukaridaki uc yer donmus koke hic bakmaz.

Tekrar calistirilabilir: tamamlanmis aylar atlanir, yarim kalan kosu kaldigi
yerden devam eder.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from fundamental_pipeline_us.point_in_time import (  # noqa: E402
    build_month_plans, freeze_price_ledger, freeze_sec_discovery_ledger,
    initialize_backtest, materialize_month_cutoff, read_json,
)
from fundamental_pipeline_us.live_refresh import (  # noqa: E402
    END_DATE, LIVE_PARENT, RUN_ID, START_DATE, month_is_complete,
    run_live_month, sec_user_agent, sync_config,
)
from fundamental_pipeline_us.sec_client import SecClient  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=24,
                    help="en yeniden geriye kac aylik kesim islensin")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rebuild", action="store_true",
                    help="koku sil ve kronolojik yeniden kur")
    args = ap.parse_args()

    root = REPO / "us" / LIVE_PARENT / RUN_ID
    if args.rebuild and root.exists():
        # Workspace ILERIYE dogru kuruldugunda (once 2026-08, sonra 2024-09)
        # degerleme sonucunun icine yazilan girdi yolu ile yeniden hesaplanan
        # yol tutmuyor ve ArtifactReferenceError geliyor. Kok turetilmis veri;
        # dogrusu KRONOLOJIK kurmak, yani bostan baslamak.
        shutil.rmtree(root)
        print(f"silindi: {root.relative_to(REPO)}  (kronolojik kurulacak)")

    if not root.is_dir():
        agent = sec_user_agent(REPO)
        root = initialize_backtest(repo_root=REPO, run_id=RUN_ID,
                                   start_date=START_DATE, end_date=END_DATE,
                                   parent=REPO / "us" / LIVE_PARENT)
        sync_config(repo_root=REPO, run_root=root)
        print("kok kuruldu, defterler donduruluyor...", flush=True)
        started = time.time()
        freeze_price_ledger(run_root=root)
        freeze_sec_discovery_ledger(run_root=root,
                                    client=SecClient(user_agent=agent))
        print(f"defterler hazir ({time.time()-started:.0f} sn)", flush=True)

    universe = read_json(root / "run-config.json")["universe"]
    plans = build_month_plans(run_root=root)
    selected = plans[-args.months:] if args.months else plans

    done, todo = [], []
    for plan in selected:
        complete = month_is_complete(run_root=root, cutoff=plan.cutoff_date,
                                     universe=universe)
        (done if complete else todo).append(plan)

    print(f"canli kok: {root.relative_to(REPO)}")
    print(f"evren {len(universe)}   secilen ay {len(selected)}   "
          f"tamam {len(done)}   islenecek {len(todo)}")
    if todo:
        print(f"  {todo[0].month} .. {todo[-1].month}")
        print(f"  tahmini sure: {len(todo) * 8.5 * len(universe) / 60:.0f} dakika")
    if args.dry_run or not todo:
        return 0

    client = SecClient(user_agent=sec_user_agent(REPO))
    started_all = time.time()
    for index, plan in enumerate(todo, start=1):
        started = time.time()
        materialize_month_cutoff(run_root=root, plan=plan)
        outcome = run_live_month(client=client, run_root=root, plan=plan,
                                 tickers=universe)
        skipped = outcome.get("skipped") or {}
        print(f"[{index}/{len(todo)}] {plan.month}  ({time.time()-started:.0f} sn, "
              f"{outcome.get('status', 'built')})"
              + (f"  ATLANAN: {', '.join(skipped)}" if skipped else ""),
              flush=True)
    print(f"\ntoplam {(time.time()-started_all)/60:.0f} dakika")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

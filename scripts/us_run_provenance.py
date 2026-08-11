"""Her kosu hangi config surumuyle uretildi, ve o surum bugun ne kadar uzakta?

Neden gerekli: donmus kosular kendi config kopyalarini tasidigi icin repo'daki
katalog degistiginde GECMISE DONUK bozulmuyorlar -- bu dogru. Ama o kosuyu
yeniden koşarsaniz yeni katalogla koşar ve ESKI SONUC TEKRAR URETILMEZ.

`run-config.json` zaten `source_config_sha256` tasiyor, ama hash size NEyin
degistigini soylemez. Bu betik farki insan okuyabilir hale getirir: hangi
dosyalar, ve metrik katalogunda kac kalem eklendi/cikti.

Kullanim:  python scripts/us_run_provenance.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from fundamental_pipeline_us.point_in_time import _tree_hash  # noqa: E402

ROOTS = [REPO / "us" / "live"]


def file_hashes(root: Path) -> dict[str, str]:
    out = {}
    if not root.is_dir():
        return out
    for path in root.rglob("*"):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()).hexdigest()
    return out


def metric_ids(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {m.get("metric_id") for m in payload.get("metrics", [])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true",
                    help="degisen dosyalari tek tek listele")
    args = ap.parse_args()

    source = REPO / "us" / "config"
    current_hash = _tree_hash(source)
    current_files = file_hashes(source)
    current_metrics = metric_ids(source / "sec" / "metric-map.json")
    print(f"su anki us/config       {current_hash[:16]}   "
          f"{len(current_files)} dosya, {len(current_metrics)} metrik\n")

    runs = []
    for parent in ROOTS:
        if parent.is_dir():
            runs += [p for p in sorted(parent.iterdir())
                     if (p / "run-config.json").is_file()]

    print(f"{'kosu':26}{'damga':>18}{'durum':>12}   fark")
    for root in runs:
        config = json.loads((root / "run-config.json").read_text(encoding="utf-8"))
        stamp = config.get("source_config_sha256") or ""
        same = stamp == current_hash
        own = root / "workspace" / "config"
        own_metrics = metric_ids(own / "sec" / "metric-map.json")
        added = sorted(current_metrics - own_metrics)
        removed = sorted(own_metrics - current_metrics)
        note = "ayni" if same else ""
        if not same:
            bits = []
            if added:
                bits.append(f"+{len(added)} metrik ({', '.join(added[:3])})")
            if removed:
                bits.append(f"-{len(removed)} metrik")
            if not bits:
                bits.append("metrik listesi ayni, baska dosya farkli")
            note = "; ".join(bits)
        label = root.relative_to(REPO).as_posix().replace("us/", "")
        print(f"{label:26}{stamp[:16]:>18}{('AYNI' if same else 'FARKLI'):>12}   {note}")
        if args.verbose and not same:
            own_files = file_hashes(own)
            for name in sorted(set(current_files) | set(own_files)):
                if "peer-universes" in name:
                    continue           # kasitli olarak cipalanmis
                if current_files.get(name) != own_files.get(name):
                    state = ("yalniz repo'da" if name not in own_files
                             else "yalniz kosuda" if name not in current_files
                             else "icerik farkli")
                    print(f"{'':26}    {name}  -- {state}")

    print("\nFARKLI olmasi kotu degil: donmus bir kosu kendi katalogunu tasir "
          "ve sonucu o katalogla uretilmistir.\nAma o kosu YENIDEN kosulursa "
          "bugunku katalogla kosar ve eski sonuc tekrar uretilmez.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

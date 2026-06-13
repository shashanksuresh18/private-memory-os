#!/usr/bin/env python3
"""Sovereign Citadel cryptographic hash-chain verifier.

Sweeps every ``*.jsonl`` file in ``audit/`` (or ``--audit-dir``) and confirms:

  1. **Chain integrity.** For each line N>1:
         record["prev_hash"] == previous_record["hash"]

  2. **Self-hash integrity.** For each line:
         record["hash"] == sha256(
             json.dumps(record_minus_hash_field,
                        sort_keys=True, ensure_ascii=False).encode("utf-8")
         )
     This matches the canonical form used by all writers in this repo
     (opf/main.py, sovereign_router.py, tools/admin/denylist_cli.py).

  3. **Operational anomaly detection** (routing.jsonl only).
     For every ``pre_egress`` record:
       * forced tier upgrade   (requested_tier != tier)
       * agent missing header  (tier_source starts with ``classifier_auto``)
       * classifier latency    (classifier_ms > --latency-threshold-ms)

Exit codes (designed for the hourly cron job in config/cron.yaml):
  0 = all logs cryptographically intact (anomalies may still be reported)
  1 = chain broken or invalid JSON detected — halt egress immediately
  2 = chain OK but anomalies exceeded threshold AND --strict was set

Usage:
    python src/routing/audit-log/verify_chain.py --audit-dir audit/
    python src/routing/audit-log/verify_chain.py --audit-dir audit/ --strict
    python src/routing/audit-log/verify_chain.py --audit-dir audit/ --quiet
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_CHAIN_BROKEN = 1
EXIT_ANOMALIES = 2

DEFAULT_LATENCY_THRESHOLD_MS = 2500
ROUTING_LOG_NAME = "routing.jsonl"


def _canonical_hash(record: dict) -> str:
    """Reproduce the writer's hash: sha256(JSON of record without 'hash' key)."""
    record_no_hash = {k: v for k, v in record.items() if k != "hash"}
    canonical = json.dumps(record_no_hash, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_log_file(
    path: Path,
    *,
    latency_threshold_ms: int = DEFAULT_LATENCY_THRESHOLD_MS,
    quiet: bool = False,
) -> tuple[bool, dict]:
    """Verify one .jsonl audit log. Returns (chain_ok, stats)."""
    is_routing_log = path.name == ROUTING_LOG_NAME

    stats: dict[str, int | None] = {
        "lines": 0,
        "broken_at": None,
        "anomalies": 0,
        "upgrades": 0,
        "misconfigs": 0,
        "latency_spikes": 0,
    }

    if not path.exists():
        print(f"[SCAN] {path.name}: file not present (no events recorded yet) -> OK")
        return True, stats

    if path.stat().st_size == 0:
        print(f"[SCAN] {path.name}: empty (no events recorded) -> OK")
        return True, stats

    print(f"[SCAN] {path.name}: verifying ...")
    prev_hash = ""
    last_seen_line = 0

    with path.open("r", encoding="utf-8") as fh:
        for line_num, raw in enumerate(fh, 1):
            line = raw.rstrip("\r\n")
            if not line.strip():
                continue
            last_seen_line = line_num

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"  [CRITICAL] line {line_num}: invalid JSON ({exc})")
                stats["broken_at"] = line_num
                return False, stats

            if not isinstance(record, dict):
                print(f"  [CRITICAL] line {line_num}: top-level value is not an object")
                stats["broken_at"] = line_num
                return False, stats

            claimed_hash = record.get("hash")
            claimed_prev = record.get("prev_hash", "")

            if not isinstance(claimed_hash, str) or len(claimed_hash) != 64:
                print(f"  [CRITICAL] line {line_num}: missing/invalid 'hash' field")
                stats["broken_at"] = line_num
                return False, stats

            if claimed_prev != prev_hash:
                print(f"  [CRITICAL] line {line_num}: prev_hash chain broken")
                print(f"             expected: {prev_hash!r}")
                print(f"             found:    {claimed_prev!r}")
                stats["broken_at"] = line_num
                return False, stats

            expected = _canonical_hash(record)
            if claimed_hash != expected:
                print(f"  [CRITICAL] line {line_num}: record self-hash mismatch")
                print(f"             expected: {expected}")
                print(f"             found:    {claimed_hash}")
                stats["broken_at"] = line_num
                return False, stats

            stats["lines"] += 1

            if is_routing_log and record.get("stage") == "pre_egress":
                tier = record.get("tier")
                req = record.get("requested_tier")
                src = record.get("tier_source", "") or ""
                cms = record.get("classifier_ms", 0)

                if req and tier and req != tier:
                    stats["upgrades"] += 1
                    stats["anomalies"] += 1
                    if not quiet:
                        print(f"  [WARN] line {line_num}: forced upgrade {req}->{tier} src={src}")

                if isinstance(src, str) and src.startswith("classifier_auto"):
                    stats["misconfigs"] += 1
                    stats["anomalies"] += 1
                    if not quiet:
                        print(f"  [WARN] line {line_num}: missing tier header -- classifier_auto fallback")

                if isinstance(cms, (int, float)) and cms > latency_threshold_ms:
                    stats["latency_spikes"] += 1
                    stats["anomalies"] += 1
                    if not quiet:
                        print(f"  [WARN] line {line_num}: classifier latency spike {int(cms)}ms")

            prev_hash = claimed_hash

    print(f"  [OK] cryptographic chain intact ({stats['lines']} records, last raw line {last_seen_line})")
    if is_routing_log and stats["anomalies"]:
        print(f"  [ANOMALIES] upgrades={stats['upgrades']} "
              f"misconfigs={stats['misconfigs']} latency_spikes={stats['latency_spikes']}")
    return True, stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Sovereign Citadel append-only audit log hash-chain verifier",
    )
    p.add_argument("--audit-dir", type=Path, default=Path("audit"),
                   help="Directory containing .jsonl logs (default: audit/)")
    p.add_argument("--latency-threshold-ms", type=int, default=DEFAULT_LATENCY_THRESHOLD_MS,
                   help="classifier_ms above this triggers a latency anomaly")
    p.add_argument("--strict", action="store_true",
                   help="Treat operational anomalies as failures (exit 2)")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress per-line WARN output; print summary only")
    args = p.parse_args(argv)

    if not args.audit_dir.exists():
        print(f"[ERROR] audit dir not found: {args.audit_dir}", file=sys.stderr)
        return EXIT_CHAIN_BROKEN

    logs = sorted(args.audit_dir.glob("*.jsonl"))
    if not logs:
        print(f"[INFO] no .jsonl logs in {args.audit_dir}")
        return EXIT_OK

    total_lines = 0
    total_anomalies = 0
    chain_broken = False

    for log in logs:
        ok, stats = verify_log_file(
            log,
            latency_threshold_ms=args.latency_threshold_ms,
            quiet=args.quiet,
        )
        total_lines += int(stats["lines"] or 0)
        total_anomalies += int(stats["anomalies"] or 0)
        if not ok:
            chain_broken = True

    print()
    if chain_broken:
        print(f"[FAIL] cryptographic verification failed across {len(logs)} log(s). "
              "Halt egress and audit immediately.")
        return EXIT_CHAIN_BROKEN

    print(f"[SUCCESS] {len(logs)} log(s) verified, {total_lines} records, "
          f"{total_anomalies} operational anomaly(ies).")

    if args.strict and total_anomalies > 0:
        print("[STRICT] anomalies present and --strict set -> exit 2")
        return EXIT_ANOMALIES
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

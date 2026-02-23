"""
Verify that all entries within each MRT bview file share the same timestamp.

Usage:
    python verify_mrt_timestamps.py /path/to/mrt_files/

    Example:
    python verify_mrt_timestamps.py /home/smotaali/First_Full_Paper/Scripts/bgp_graph_features/data/mrt_files

This script parses every bview.*.gz file in the given directory and reports
the unique timestamps found inside each file. If all entries share the same
timestamp, the file is marked as PASS. Otherwise, it is marked as FAIL with
details about the timestamp spread.
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

try:
    import bgpkit
except ImportError:
    print("ERROR: pybgpkit is not installed. Run: pip install pybgpkit")
    sys.exit(1)


def analyze_mrt_file(file_path: Path) -> dict:
    """Parse a single MRT file and return timestamp statistics."""
    print(f"\n  Parsing: {file_path.name} ({file_path.stat().st_size / (1024*1024):.1f} MB)")

    t0 = time.time()
    timestamps = []
    count = 0

    parser = bgpkit.Parser(url=str(file_path))
    for elem in parser:
        timestamps.append(elem.timestamp)
        count += 1

    elapsed = time.time() - t0

    if count == 0:
        return {"file": file_path.name, "total_elements": 0, "error": "no elements"}

    # Count unique timestamps
    ts_counter = Counter(timestamps)
    unique_count = len(ts_counter)

    # Convert to readable
    readable_counter = {}
    for raw_ts, cnt in ts_counter.items():
        label = datetime.fromtimestamp(raw_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        readable_counter[label] = cnt

    spread_seconds = max(timestamps) - min(timestamps)

    result = {
        "file": file_path.name,
        "total_elements": count,
        "unique_timestamps": unique_count,
        "timestamps": readable_counter,
        "spread_seconds": spread_seconds,
        "parse_time": round(elapsed, 1),
        "pass": unique_count == 1,
    }

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python verify_mrt_timestamps.py /path/to/mrt_files/")
        print("\nExample:")
        print("  python verify_mrt_timestamps.py ./bgp_graph_features/data/mrt_files")
        sys.exit(1)

    mrt_dir = Path(sys.argv[1])
    if not mrt_dir.is_dir():
        print(f"ERROR: {mrt_dir} is not a directory")
        sys.exit(1)

    # Find all bview files
    bview_files = sorted(mrt_dir.glob("bview.*.gz"))
    if not bview_files:
        print(f"ERROR: No bview.*.gz files found in {mrt_dir}")
        sys.exit(1)

    print("=" * 70)
    print("MRT TIMESTAMP VERIFICATION")
    print("=" * 70)
    print(f"Directory: {mrt_dir}")
    print(f"Files found: {len(bview_files)}")

    results = []
    for f in bview_files:
        result = analyze_mrt_file(f)
        results.append(result)

        # Print per-file result immediately
        status = "PASS" if result["pass"] else "FAIL"
        print(f"  -> [{status}] {result['total_elements']:>10,} elements, "
              f"{result['unique_timestamps']} unique timestamp(s), "
              f"spread={result['spread_seconds']:.0f}s, "
              f"parsed in {result['parse_time']}s")
        for ts_label, cnt in sorted(result["timestamps"].items()):
            pct = cnt / result["total_elements"] * 100
            print(f"       {ts_label}  :  {cnt:>10,} elements ({pct:.2f}%)")

    # Summary
    n_pass = sum(1 for r in results if r["pass"])
    n_fail = sum(1 for r in results if not r["pass"])

    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total files:  {len(results)}")
    print(f"  PASS:         {n_pass}  (all elements share one timestamp)")
    print(f"  FAIL:         {n_fail}  (multiple timestamps found)")

    if n_fail == 0:
        print(f"\n  CONCLUSION: All {n_pass} bview files have a single uniform timestamp.")
        print(f"  The 'one file = one snapshot' assumption is VERIFIED.")
    else:
        print(f"\n  WARNING: {n_fail} file(s) contain multiple timestamps!")
        print(f"  Files with multiple timestamps:")
        for r in results:
            if not r["pass"]:
                print(f"    - {r['file']}: {r['unique_timestamps']} timestamps, "
                      f"spread={r['spread_seconds']:.0f}s")

    print()


if __name__ == "__main__":
    main()

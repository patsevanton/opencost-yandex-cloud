#!/usr/bin/env python3
import argparse
import json
import urllib.error
import urllib.parse
import urllib.request


def _read_lines(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f.read().splitlines() if ln.strip()]


def _fetch_metric_names(vm_base_url: str, tenant: str, start: str | None, end: str | None, match: str | None) -> list[str]:
    base = vm_base_url.rstrip("/")
    url = f"{base}/api/v1/label/__name__/values"
    params: dict[str, str] = {}
    if tenant:
        params["tenant"] = tenant
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    if match:
        params["match[]"] = match
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} from {url}\n{detail}".strip()) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to reach {url}: {e}") from e

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Non-JSON response from {url}") from e

    if payload.get("status") != "success":
        raise RuntimeError(f"Unexpected response from {url}: {payload}")

    data = payload.get("data")
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected data shape from {url}: {payload}")

    out: list[str] = []
    for x in data:
        if isinstance(x, str) and x:
            out.append(x)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Compare metric names from VictoriaMetrics with names in a local file (one metric per line)."
    )
    ap.add_argument(
        "--vm-url",
        required=True,
        help="VictoriaMetrics base URL (e.g. http://localhost:8428 after kubectl port-forward).",
    )
    ap.add_argument(
        "--file",
        default="opencost_metrics.txt",
        help="Path to the local metrics file (default: opencost_metrics.txt)",
    )
    ap.add_argument(
        "--tenant",
        default="",
        help="Optional VictoriaMetrics tenant. For multi-tenant use 'accountID:projectID'.",
    )
    ap.add_argument("--start", default=None, help="Optional start time (unix seconds or RFC3339).")
    ap.add_argument("--end", default=None, help="Optional end time (unix seconds or RFC3339).")
    ap.add_argument(
        "--match",
        default=None,
        help="Optional series selector to limit metric name extraction, e.g. '{job=~\"opencost|kubecost\"}'.",
    )
    ap.add_argument("--json", action="store_true", help="Output result as JSON.")
    args = ap.parse_args()

    want = sorted(set(_read_lines(args.file)))
    have = sorted(set(_fetch_metric_names(args.vm_url, args.tenant, args.start, args.end, args.match)))

    want_set = set(want)
    have_set = set(have)

    matched = sorted(want_set & have_set)
    matched = [m for m in matched if not m.startswith("go_")]
    missing_in_vm = sorted(want_set - have_set)
    extra_in_vm = sorted(have_set - want_set)

    result = {
        "file_count": len(want),
        "vm_count": len(have),
        "matched_count": len(matched),
        "missing_in_vm_count": len(missing_in_vm),
        "extra_in_vm_count": len(extra_in_vm),
        "matched": matched,
        "missing_in_vm": missing_in_vm,
        "extra_in_vm": extra_in_vm,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"matched: {len(matched)}")
    for m in matched:
        print(m)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

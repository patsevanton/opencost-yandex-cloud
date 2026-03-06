#!/usr/bin/env python3
"""
Find which Grafana dashboards use a given list of metric names.
Uses Grafana HTTP API (search + get dashboard by uid).
"""
import argparse
import json
import re
import urllib.error
import urllib.request


def _request(grafana_url: str, path: str, api_key: str) -> bytes:
    base = grafana_url.rstrip("/")
    url = f"{base}{path}"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def search_dashboards(grafana_url: str, api_key: str) -> list[dict]:
    """Return list of dashboard items: uid, title, etc."""
    body = _request(grafana_url, "/api/search?type=dash-db&limit=5000", api_key)
    data = json.loads(body)
    if not isinstance(data, list):
        return []
    return [{"uid": d.get("uid"), "title": d.get("title", "?")} for d in data if d.get("uid")]


def get_dashboard_json(grafana_url: str, api_key: str, uid: str) -> dict | None:
    """Return dashboard JSON (dashboard key holds the spec)."""
    body = _request(grafana_url, f"/api/dashboards/uid/{uid}", api_key)
    data = json.loads(body)
    return data.get("dashboard") if isinstance(data, dict) else None


def dashboard_text(dashboard: dict) -> str:
    """Serialize dashboard to string for metric search (panels, targets, expressions)."""
    return json.dumps(dashboard, ensure_ascii=False)


def find_metrics_in_text(text: str, metrics: list[str]) -> list[str]:
    """Return metric names that appear in text (exact name, e.g. not suffix like _cpu_cores)."""
    found = []
    for m in metrics:
        # Metric name as word: followed by {, space, ", ], ), or end
        pattern = re.escape(m) + r"(?=[{\s\"\]\)]|$)"
        if re.search(pattern, text):
            found.append(m)
    return found


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Find which Grafana dashboards use the given metric names (e.g. from compare_vm_metrics.py)."
    )
    ap.add_argument(
        "--grafana-url",
        default="http://localhost:3000",
        help="Grafana base URL (default: http://localhost:3000)",
    )
    ap.add_argument(
        "--api-key",
        default="",
        help="Grafana API key or service account token (or set GRAFANA_API_KEY).",
    )
    ap.add_argument(
        "--metrics",
        nargs="+",
        default=None,
        help="Metric names to look for. If omitted, reads from stdin (one per line).",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON.",
    )
    args = ap.parse_args()

    api_key = args.api_key or __import__("os").environ.get("GRAFANA_API_KEY", "")

    if args.metrics:
        metrics = list(args.metrics)
    else:
        metrics = [ln.strip() for ln in __import__("sys").stdin.read().splitlines() if ln.strip()]
    if not metrics:
        print("No metrics to search. Pass --metrics or pipe a list.", file=__import__("sys").stderr)
        return 1

    try:
        dashboards = search_dashboards(args.grafana_url, api_key)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Grafana search failed: HTTP {e.code}\n{body}", file=__import__("sys").stderr)
        return 1
    except Exception as e:
        print(f"Grafana request failed: {e}", file=__import__("sys").stderr)
        return 1

    # metric -> list of dashboard titles
    metric_to_dashboards: dict[str, list[str]] = {m: [] for m in metrics}
    # dashboard title -> list of metrics used
    dashboard_to_metrics: dict[str, list[str]] = {}

    for d in dashboards:
        uid, title = d["uid"], d["title"]
        try:
            dashboard = get_dashboard_json(args.grafana_url, api_key, uid)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            print(f"Skip dashboard {title!r}: HTTP {e.code}", file=__import__("sys").stderr)
            continue
        except Exception as e:
            print(f"Skip dashboard {title!r}: {e}", file=__import__("sys").stderr)
            continue
        if not dashboard:
            continue
        text = dashboard_text(dashboard)
        used = find_metrics_in_text(text, metrics)
        if not used:
            continue
        dashboard_to_metrics[title] = used
        for m in used:
            metric_to_dashboards[m].append(title)

    result = {
        "grafana_url": args.grafana_url,
        "metrics_searched": len(metrics),
        "dashboards_scanned": len(dashboards),
        "dashboards_using_metrics": len(dashboard_to_metrics),
        "metric_to_dashboards": metric_to_dashboards,
        "dashboard_to_metrics": dashboard_to_metrics,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # Human-readable
    used_metrics = [m for m in metrics if metric_to_dashboards[m]]
    unused_metrics = [m for m in metrics if not metric_to_dashboards[m]]
    print(f"Dashboards scanned: {len(dashboards)}")
    print(f"Dashboards using any of the {len(metrics)} metrics: {len(dashboard_to_metrics)}")
    print()
    if dashboard_to_metrics:
        print("Dashboards and metrics used:")
        for title in sorted(dashboard_to_metrics.keys()):
            mlist = sorted(dashboard_to_metrics[title])
            print(f"  {title}")
            for m in mlist:
                print(f"    - {m}")
        print()
    print(f"Metrics used in at least one dashboard: {len(used_metrics)}")
    for m in sorted(used_metrics):
        dashs = sorted(metric_to_dashboards[m])
        print(f"  {m}")
        for d in dashs:
            print(f"    -> {d}")
    print()
    print(f"Metrics not found in any dashboard: {len(unused_metrics)}")
    for m in sorted(unused_metrics):
        print(f"  {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

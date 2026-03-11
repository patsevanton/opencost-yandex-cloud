#!/usr/bin/env python3
"""
Получение тарифов Yandex Cloud из Billing API (Sku.List) и подстановка в custom-pricing-configmap.yaml.

Требуется IAM-токен: export IAM_TOKEN=$(yc iam create-token)
Или передать через --token.

Использование:
  # Только вывести подобранные цены (рубли):
  python3 scripts/fetch_yandex_sku_prices.py

  # Список всех SKU (с пагинацией): id, serviceId, unit, price, name
  python3 scripts/fetch_yandex_sku_prices.py --list-skus

  # То же и сохранить в файл (например skus.txt):
  python3 scripts/fetch_yandex_sku_prices.py --list-skus --output skus.txt

  # Обновить custom-pricing-configmap.yaml:
  python3 scripts/fetch_yandex_sku_prices.py --update custom-pricing-configmap.yaml

"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BILLING_SKUS_URL = "https://billing.api.cloud.yandex.net/billing/v1/skus"
HOURS_PER_MONTH = 730


def _get(obj: dict, *keys: str, default=None):
    """Достать значение по одному из ключей (snake_case или camelCase)."""
    for k in keys:
        for key in (k, _to_camel(k), _to_snake(k)):
            if key in obj:
                return obj[key]
    return default


def _to_camel(s: str) -> str:
    parts = s.lower().split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _to_snake(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()


def fetch_skus(token: str) -> tuple[dict, list[dict]]:
    """Загрузить список SKU из Billing API с учётом пагинации. Возвращает (последний ответ API, полный список skus)."""
    all_skus: list[dict] = []
    page_token: str | None = None
    last_data: dict = {}

    while True:
        url = BILLING_SKUS_URL
        if page_token:
            url = f"{url}?{urlencode({'pageToken': page_token})}"
        req = Request(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="GET",
        )
        try:
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except (HTTPError, URLError) as e:
            sys.exit(f"Ошибка запроса к Billing API: {e}")

        last_data = data
        skus = _get(data, "skus")
        if skus is None:
            skus = data if isinstance(data, list) else []
        if not isinstance(skus, list):
            skus = [skus]
        all_skus.extend(skus)

        page_token = _get(data, "next_page_token", "nextPageToken")
        if not page_token:
            break

    return last_data, all_skus


def _current_unit_price_rub(sku: dict) -> float | None:
    """Извлечь текущую цену за единицу в рублях. unitPrice может быть в копейках."""
    versions = _get(sku, "pricing_versions", "pricingVersions") or []
    if not versions:
        return None
    # Берём последнюю по effective_time (текущую)
    versions = sorted(
        versions,
        key=lambda v: _get(v, "effective_time", "effectiveTime") or "",
        reverse=True,
    )
    for ver in versions:
        exprs = _get(ver, "pricing_expressions", "pricingExpressions") or []
        for expr in exprs:
            rates = _get(expr, "rates") or []
            for rate in rates:
                price = _get(rate, "unit_price", "unitPrice")
                if price is None:
                    continue
                try:
                    unit_price = float(price)
                except (TypeError, ValueError):
                    continue
                currency = (_get(rate, "currency") or "RUB").upper()
                if currency == "RUB" and unit_price >= 0:
                    # Цена в API часто в копейках; если значение > 100 — похоже на копейки
                    if unit_price >= 10 and unit_price < 1_000_000:
                        unit_price = unit_price / 100.0
                    return round(unit_price, 4)
                elif currency == "RUB":
                    return round(unit_price, 4)
    return None


def _pricing_unit(sku: dict) -> str:
    u = _get(sku, "pricing_unit", "pricingUnit") or ""
    return (u or "").lower().replace("*", "_").replace("-", "_")


def _name_and_desc(sku: dict) -> str:
    name = _get(sku, "name") or ""
    desc = _get(sku, "description") or ""
    return (name + " " + desc).lower()


def list_skus_text(skus: list[dict]) -> str:
    """Сформировать текст списка SKU (id, serviceId, pricingUnit, price, name, description) для вывода или сохранения в файл."""
    lines = [
        "SKU из Billing API (Sku.List), страницы объединены: id\tserviceId\tpricingUnit\tprice\tname\tdescription",
        f"Всего SKU: {len(skus)}",
    ]
    for sku in skus:
        price = _current_unit_price_rub(sku)
        pid = _get(sku, "id") or ""
        svc = _get(sku, "service_id", "serviceId") or ""
        name = _get(sku, "name") or ""
        desc = (_get(sku, "description") or "")[:80]
        unit = _pricing_unit(sku)
        pstr = f"{price} RUB" if price is not None else "—"
        lines.append(f"  {pid}\t{svc}\t{unit}\t{pstr}\t{name}\t{desc}")
    return "\n".join(lines)


def list_skus(skus: list[dict]) -> None:
    """Вывести список SKU в stdout."""
    print(list_skus_text(skus))


def _is_compute_cloud_regular_vm(text: str) -> bool:
    """SKU относится к Compute Cloud, обычные VM (не Preemptible, не Data Processing, не Managed Service)."""
    t = text
    if "preemptible" in t or "data processing" in t or "data proc" in t or "managed service" in t:
        return False
    return "regular vm" in t or ("compute" in t and "vm" in t) or "вычислительные ресурсы обычной" in t


def _is_vm_disk(text: str) -> bool:
    """Диск, привязанный к VM (Compute Cloud), не Object Storage / ice / video / Cloud Desktop."""
    t = text
    if "object storage" in t or "ice storage" in t or "cloud video" in t or "cloud desktop" in t:
        return False
    if "data placement" in t and "ice" in t:
        return False
    return ("disk" in t or "диск" in t or "drive" in t) and ("standard" in t or "fast" in t or "hdd" in t or "ssd" in t or "network drive" in t)


def _is_plain_ice_lake_cpu(text: str) -> bool:
    """Intel Ice Lake без GPU (T4/T4i/Nvidia) и без Compute Optimized."""
    t = text
    if "t4i" in t or "t4 " in t or "nvidia" in t or "compute optimized" in t:
        return False
    return "ice lake" in t and "100%" in t


def _is_plain_ram(text: str) -> bool:
    """RAM: Intel Ice Lake, без GPU PLATFORM V4, без Compute Optimized, без T4/Nvidia/V100."""
    t = text
    if "gpu platform" in t or "platform v4" in t or "compute optimized" in t or "t4i" in t or "nvidia" in t or "v100" in t:
        return False
    return "ram" in t and "ice lake" in t


def match_skus(skus: list[dict]) -> tuple[dict[str, float], dict[str, str]]:
    """
    Сопоставить SKU с полями ConfigMap: CPU, RAM, storage.
    Приоритет: Compute Cloud, Regular VM, 100% vCPU; диски ВМ (не Object Storage).
    Возвращает (словарь ключ -> месячная ставка в рублях, словарь ключ -> название SKU).
    """
    result: dict[str, float] = {}
    cpu_candidates: list[tuple[float, str]] = []
    cpu_preferred: list[tuple[float, str]] = []  # Regular VM, просто Intel Ice Lake (без GPU, без Compute Optimized)
    ram_candidates: list[tuple[float, str]] = []
    ram_preferred: list[tuple[float, str]] = []  # Regular VM, Intel Ice Lake RAM (не GPU PLATFORM V4)
    storage_candidates: list[tuple[float, str]] = []
    storage_preferred: list[tuple[float, str]] = []  # SSD, не Cloud Desktop

    for sku in skus:
        unit = _pricing_unit(sku)
        text = _name_and_desc(sku)
        price = _current_unit_price_rub(sku)
        if price is None:
            continue
        name = _get(sku, "name") or sku.get("id", "")

        # vCPU: приоритет — Regular VM, просто Intel Ice Lake 100% vCPU (без T4/Nvidia, без CVoS)
        if "core" in unit and "hour" in unit:
            cpu_candidates.append((price, name))
            if _is_compute_cloud_regular_vm(text) and _is_plain_ice_lake_cpu(text) and "cvos" not in text:
                cpu_preferred.append((price, name))

        # RAM: приоритет — Regular VM, просто RAM (без Compute Optimized, без CVoS)
        if "gbyte" in unit and "hour" in unit:
            if "disk" in text or "диск" in text or "storage" in text and "ram" not in text:
                if _is_vm_disk(text):
                    storage_candidates.append((price, name))
                    if "ssd" in text and ("fast" in text or "network drive" in text):
                        storage_preferred.append((price, name))
            elif "ram" in text or "память" in text or "memory" in text or ("gb" in text and "disk" not in text and "диск" not in text):
                ram_candidates.append((price, name))
                if _is_compute_cloud_regular_vm(text) and "cvos" not in text and _is_plain_ram(text):
                    ram_preferred.append((price, name))

        # Диск ВМ: приоритет SSD, не Cloud Desktop (_is_vm_disk уже исключает cloud desktop)
        if "gbyte" in unit and "hour" in unit and _is_vm_disk(text):
            storage_candidates.append((price, name))
            if "ssd" in text and ("fast" in text or "network drive" in text):
                storage_preferred.append((price, name))

    def _min_positive_candidate(candidates: list[tuple[float, str]]) -> tuple[float, str] | None:
        positive = [(p, n) for p, n in candidates if p > 0]
        if not positive:
            return None
        return min(positive, key=lambda x: x[0])

    def _choose_with_name(
        preferred: list[tuple[float, str]], fallback: list[tuple[float, str]]
    ) -> tuple[float, str] | None:
        c = _min_positive_candidate(preferred)
        if c is not None:
            return c
        return _min_positive_candidate(fallback)

    names: dict[str, str] = {}
    if cpu_candidates:
        chosen = _choose_with_name(cpu_preferred, cpu_candidates)
        if chosen is not None:
            price, name = chosen
            result["CPU"] = round(price * HOURS_PER_MONTH, 3)
            names["CPU"] = name
    if ram_candidates:
        chosen = _choose_with_name(ram_preferred, ram_candidates)
        if chosen is not None:
            price, name = chosen
            result["RAM"] = round(price * HOURS_PER_MONTH, 3)
            names["RAM"] = name
    if storage_candidates:
        chosen = _choose_with_name(storage_preferred, storage_candidates)
        if chosen is not None:
            price, name = chosen
            result["storage"] = round(price * HOURS_PER_MONTH, 3)
            names["storage"] = name

    return result, names


def update_configmap(
    configmap_path: Path,
    prices: dict[str, float],
    names: dict[str, str] | None = None,
) -> None:
    """Обновить в YAML значения CPU, RAM, storage."""
    names = names or {}
    text = configmap_path.read_text(encoding="utf-8")
    for key in ("CPU", "RAM", "storage"):
        if key not in prices:
            continue
        val = prices[key]
        hourly = val / HOURS_PER_MONTH
        unit = "vCPU-час" if key == "CPU" else "ГБ-час"
        name_part = f" ({names.get(key, '').strip()})" if names.get(key) else ""
        comment = f"  # {hourly:.4f} ₽/{unit}{name_part} * 730"
        # Для storage только подставляем значение.
        pattern = re.compile(
            r'^(\s*' + re.escape(key) + r':\s*)"[^"]*"(.*)$',
            re.MULTILINE,
        )
        if key == "storage":
            replacement = rf'\1"{val}"\2'
        else:
            replacement = rf'\1"{val}"' + comment
        new_text = pattern.sub(replacement, text, count=1)
        if new_text != text:
            text = new_text
        else:
            pattern2 = re.compile(
                r'^(\s*' + re.escape(key) + r':\s*)[^\s#]+(.*)$',
                re.MULTILINE,
            )
            repl2 = rf'\1"{val}"\2' if key == "storage" else rf'\1"{val}"' + comment
            text = pattern2.sub(repl2, text, count=1)
    configmap_path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Получить тарифы из Yandex Billing API и опционально обновить custom-pricing-configmap.yaml",
    )
    parser.add_argument(
        "--token",
        "-t",
        default=os.environ.get("IAM_TOKEN"),
        help="IAM-токен (или переменная IAM_TOKEN)",
    )
    parser.add_argument(
        "--update",
        "-u",
        type=Path,
        metavar="FILE",
        help="Путь к custom-pricing-configmap.yaml для обновления",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только вывести подобранные цены, не менять файлы",
    )
    parser.add_argument(
        "--list-skus",
        action="store_true",
        help="Вывести список всех SKU из каталога (id, serviceId, unit, price, name) для сравнения с полями ConfigMap",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        metavar="FILE",
        help="Сохранить вывод --list-skus в txt-файл",
    )
    args = parser.parse_args()

    token = args.token
    if not token:
        import subprocess
        try:
            token = subprocess.run(
                ["yc", "iam", "create-token"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            ).stdout.strip()
        except FileNotFoundError:
            pass
    if not token:
        print("Задайте IAM_TOKEN или --token, либо установите yc CLI и выполните: yc iam create-token", file=sys.stderr)
        return 2

    raw_response, skus = fetch_skus(token)
    if not skus:
        print("SKU не получены или список пуст. Проверьте токен и права доступа к Billing API.", file=sys.stderr)
        return 1

    if args.list_skus:
        text = list_skus_text(skus)
        print(text)
        if args.output is not None:
            args.output.write_text(text, encoding="utf-8")
            print(f"Сохранено в {args.output}", file=sys.stderr)
        return 0

    prices, names = match_skus(skus)
    if not prices:
        print("Не удалось сопоставить ни один SKU с CPU/RAM/storage. Проверьте токен и структуру ответа API.", file=sys.stderr)
        return 1

    print("Подобранные тарифы (рубли):")
    for k, v in prices.items():
        name_info = f" — {names.get(k, '')}" if names.get(k) else ""
        print(f"  {k}: {v}  (мес, почасовая {v / HOURS_PER_MONTH:.4f}){name_info}")

    if args.update and not args.dry_run:
        update_configmap(args.update, prices, names)
        print(f"Обновлён файл: {args.update}")
    elif args.update and args.dry_run:
        print("Dry-run: файл не изменён.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

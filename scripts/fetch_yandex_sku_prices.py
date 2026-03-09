#!/usr/bin/env python3
"""
Получение тарифов Yandex Cloud из Billing API (Sku.List) и подстановка в custom-pricing-configmap.yaml.

Требуется IAM-токен: export IAM_TOKEN=$(yc iam create-token)
Или передать через --token.

Использование:
  # Только вывести подобранные цены (рубли):
  python3 scripts/fetch_yandex_sku_prices.py

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


def fetch_skus(token: str) -> list[dict]:
    """Загрузить список SKU из Billing API."""
    req = Request(
        BILLING_SKUS_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except (HTTPError, URLError) as e:
        sys.exit(f"Ошибка запроса к Billing API: {e}")

    skus = _get(data, "skus")
    if skus is None:
        skus = data if isinstance(data, list) else []
    if not isinstance(skus, list):
        skus = [skus]

    return skus


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


def list_skus(skus: list[dict]) -> None:
    """Вывести список SKU из каталога (id, name, description, pricingUnit, price RUB) для сравнения с полями ConfigMap."""
    for sku in skus:
        price = _current_unit_price_rub(sku)
        pid = _get(sku, "id") or ""
        name = _get(sku, "name") or ""
        desc = (_get(sku, "description") or "")[:80]
        unit = _pricing_unit(sku)
        svc = _get(sku, "service_id", "serviceId") or ""
        pstr = f"{price} RUB" if price is not None else "—"
        print(f"  {pid}\t{unit}\t{pstr}\t{name}\t{desc}")


def match_skus(skus: list[dict]) -> dict[str, float]:
    """
    Сопоставить SKU с полями ConfigMap: CPU, RAM, storage.
    Возвращает словарь ключ -> значение в рублях (месячные ставки).
    """
    result: dict[str, float] = {}
    cpu_candidates: list[tuple[float, str]] = []
    ram_candidates: list[tuple[float, str]] = []
    storage_candidates: list[tuple[float, str]] = []

    for sku in skus:
        unit = _pricing_unit(sku)
        text = _name_and_desc(sku)
        price = _current_unit_price_rub(sku)
        if price is None:
            continue

        # vCPU: core*hour, core-hour, упоминание vcpu/cpu
        if "core" in unit and "hour" in unit:
            cpu_candidates.append((price, _get(sku, "name") or sku.get("id", "")))
        elif "cpu" in text or "vpu" in text or "core" in text:
            if "hour" in unit or "час" in text:
                cpu_candidates.append((price, _get(sku, "name") or ""))

        # RAM: gbyte*hour для памяти (не диска)
        if "gbyte" in unit and "hour" in unit:
            if "ram" in text or "память" in text or "memory" in text or "gb" in text and "disk" not in text and "диск" not in text:
                ram_candidates.append((price, _get(sku, "name") or ""))
            elif "disk" in text or "диск" in text or "storage" in text or "nvme" in text or "ssd" in text or "hdd" in text:
                storage_candidates.append((price, _get(sku, "name") or ""))
            elif not storage_candidates and not ram_candidates:
                ram_candidates.append((price, _get(sku, "name") or ""))

        # Диск: gbyte*hour для диска
        if "gbyte" in unit and "hour" in unit and ("disk" in text or "диск" in text or "storage" in text or "ssd" in text or "hdd" in text or "nvme" in text):
            storage_candidates.append((price, _get(sku, "name") or ""))

    def _min_positive(candidates: list[tuple[float, str]]) -> float | None:
        prices = [c[0] for c in candidates if c[0] > 0]
        return min(prices) if prices else None

    if cpu_candidates:
        price = _min_positive(cpu_candidates)
        if price is not None:
            result["CPU"] = round(price * HOURS_PER_MONTH, 3)
    if ram_candidates:
        price = _min_positive(ram_candidates)
        if price is not None:
            result["RAM"] = round(price * HOURS_PER_MONTH, 3)
    if storage_candidates:
        price = _min_positive(storage_candidates)
        if price is not None:
            result["storage"] = round(price * HOURS_PER_MONTH, 3)

    return result


def update_configmap(configmap_path: Path, prices: dict[str, float]) -> None:
    """Обновить в YAML значения CPU, RAM, storage, сохраняя комментарии и структуру."""
    text = configmap_path.read_text(encoding="utf-8")
    for key in ("CPU", "RAM", "storage"):
        if key not in prices:
            continue
        val = prices[key]
        hourly = val / HOURS_PER_MONTH
        unit = "vCPU-час" if key == "CPU" else "ГБ-час"
        comment = f"  # {hourly:.4f} ₽/{unit} * 730"
        pattern = re.compile(
            r'^(\s*' + re.escape(key) + r':\s*)"[^"]*"(.*)$',
            re.MULTILINE,
        )
        replacement = rf'\1"{val}"' + comment + r"\2"
        new_text = pattern.sub(replacement, text, count=1)
        if new_text != text:
            text = new_text
        else:
            pattern2 = re.compile(
                r'^(\s*' + re.escape(key) + r':\s*)[^\s#]+(.*)$',
                re.MULTILINE,
            )
            text = pattern2.sub(rf'\1"{val}"' + comment + r"\2", text, count=1)
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
        "--save-response",
        type=Path,
        metavar="FILE",
        help="Сохранить сырой JSON ответа API в файл",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только вывести подобранные цены, не менять файлы",
    )
    parser.add_argument(
        "--list-skus",
        action="store_true",
        help="Вывести список всех SKU из каталога (id, unit, price, name) для сравнения с полями ConfigMap",
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

    skus = fetch_skus(token)
    if not skus:
        print("SKU не получены или список пуст. Проверьте токен и права доступа к Billing API.", file=sys.stderr)
        return 1

    if args.list_skus:
        print("SKU из Billing API (Sku.List): id\tpricingUnit\tprice\tname\tdescription")
        list_skus(skus)
        return 0

    prices = match_skus(skus)
    if not prices:
        print("Не удалось сопоставить ни один SKU с CPU/RAM/storage. Проверьте токен и структуру ответа API.", file=sys.stderr)
        return 1

    print("Подобранные тарифы (рубли):")
    for k, v in prices.items():
        print(f"  {k}: {v}  (мес, почасовая {v / HOURS_PER_MONTH:.4f})")

    if args.update and not args.dry_run:
        update_configmap(args.update, prices)
        print(f"Обновлён файл: {args.update}")
    elif args.update and args.dry_run:
        print("Dry-run: файл не изменён.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

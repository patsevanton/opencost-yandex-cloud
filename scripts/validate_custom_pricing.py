#!/usr/bin/env python3
"""
Проверка custom-pricing ConfigMap для OpenCost.

Читает ConfigMap из YAML-файла или stdin (kubectl get configmap ... -o yaml),
проверяет наличие обязательных ключей и что числовые значения в разумных диапазонах.

Использование:
  python3 scripts/validate_custom_pricing.py --file custom-pricing-configmap.yaml
  kubectl get configmap custom-pricing-model -n opencost -o yaml | python3 scripts/validate_custom_pricing.py --stdin
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def load_yaml(content: str):
    try:
        import yaml
    except ImportError:
        sys.exit("Need PyYAML: pip install pyyaml")
    return yaml.safe_load(content)


def extract_data(doc: dict) -> dict[str, str] | None:
    """Из документа ConfigMap достаём data; иначе считаем, что передан сам data."""
    if not doc or not isinstance(doc, dict):
        return None
    if "data" in doc and isinstance(doc["data"], dict):
        return doc["data"]
    # Передан голый data-блок
    return doc


REQUIRED_KEYS = ("provider", "CPU", "RAM", "storage")
OPTIONAL_KEYS = (
    "description",
    "zoneNetworkEgress",
    "regionNetworkEgress",
    "internetNetworkEgress",
    "LBIngressDataCost",
    "FirstFiveForwardingRulesCost",
    "AdditionalForwardingRuleCost",
)
NUMERIC_KEYS = (
    "CPU",
    "RAM",
    "storage",
    "zoneNetworkEgress",
    "regionNetworkEgress",
    "internetNetworkEgress",
    "LBIngressDataCost",
    "FirstFiveForwardingRulesCost",
    "AdditionalForwardingRuleCost",
)
# Разумные диапазоны (₽): месячные CPU/RAM/storage — от копеек до сотен тысяч за единицу
MIN_MONTHLY_PER_UNIT = 0.01
MAX_MONTHLY_PER_UNIT = 500_000.0
MIN_EGRESS_PER_GB = 0.0
MAX_EGRESS_PER_GB = 100.0


def strip_comment(value: str) -> str:
    """Убирает комментарий из значения (например ' "938.196" # 1.2852 * 730')."""
    if "#" in value:
        value = value.split("#", 1)[0]
    return value.strip().strip('"').strip("'").strip()


def parse_float(s: str) -> float | None:
    s = strip_comment(str(s))
    try:
        return float(s)
    except ValueError:
        return None


def validate(data: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if not data:
        errors.append("data пустой или отсутствует")
        return errors

    for key in REQUIRED_KEYS:
        if key not in data:
            errors.append(f"Отсутствует обязательный ключ: {key}")

    for key in NUMERIC_KEYS:
        if key not in data:
            continue
        raw = data[key]
        val = parse_float(raw)
        if val is None:
            errors.append(f"{key}: не удалось разобрать число из '{raw[:50]}'")
            continue
        if key in ("CPU", "RAM", "storage"):
            if val < MIN_MONTHLY_PER_UNIT or val > MAX_MONTHLY_PER_UNIT:
                errors.append(
                    f"{key}: значение {val} вне ожидаемого диапазона "
                    f"({MIN_MONTHLY_PER_UNIT}..{MAX_MONTHLY_PER_UNIT} ₽/мес)"
                )
        elif "Egress" in key or "Network" in key:
            if val < MIN_EGRESS_PER_GB or val > MAX_EGRESS_PER_GB:
                errors.append(
                    f"{key}: значение {val} вне ожидаемого диапазона "
                    f"({MIN_EGRESS_PER_GB}..{MAX_EGRESS_PER_GB} ₽/ГБ)"
                )
        # LB-поля могут быть 0 или небольшие числа — только проверяем, что число
        elif val < 0:
            errors.append(f"{key}: ожидается неотрицательное число, получено {val}")

    # Проверка согласованности почасовой ставки (опционально): hourly * 730 ≈ monthly
    for key in ("CPU", "RAM", "storage"):
        if key not in data:
            continue
        val = parse_float(data[key])
        if val is None:
            continue
        hourly_from_monthly = val / 730.0
        # Проверяем только порядок величины: типичные ₽/час для vCPU/RAM/диска в РФ
        if key == "CPU" and not (0.1 <= hourly_from_monthly <= 50):
            errors.append(
                f"{key}: месячная ставка {val} даёт {hourly_from_monthly:.4f} ₽/час; "
                "проверьте, что указана месячная ставка (почасовая * 730)"
            )
        elif key == "RAM" and not (0.01 <= hourly_from_monthly <= 20):
            errors.append(
                f"{key}: месячная ставка {val} даёт {hourly_from_monthly:.4f} ₽/час; "
                "проверьте расчёт (почасовая * 730)"
            )
        elif key == "storage" and not (0.001 <= hourly_from_monthly <= 5):
            errors.append(
                f"{key}: месячная ставка {val} даёт {hourly_from_monthly:.4f} ₽/час; "
                "проверьте расчёт (почасовая * 730)"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Проверка custom-pricing ConfigMap для OpenCost"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", "-f", type=Path, help="Путь к YAML-файлу ConfigMap")
    group.add_argument("--stdin", action="store_true", help="Читать YAML из stdin")
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Выводить только ошибки (exit 1 при наличии ошибок)",
    )
    args = parser.parse_args()

    if args.file:
        content = args.file.read_text(encoding="utf-8")
    else:
        content = sys.stdin.read()

    doc = load_yaml(content)
    data = extract_data(doc)
    if data is None:
        print("Ошибка: не найден блок data в YAML", file=sys.stderr)
        return 2

    errors = validate(data)
    if errors:
        if not args.quiet:
            print("Обнаружены ошибки валидации:", file=sys.stderr)
            for e in errors:
                print("  -", e, file=sys.stderr)
        return 1

    if not args.quiet:
        print("OK: все проверки пройдены.")
        print("  CPU (₽/мес):", strip_comment(data.get("CPU", "")))
        print("  RAM (₽/мес):", strip_comment(data.get("RAM", "")))
        print("  storage (₽/мес):", strip_comment(data.get("storage", "")))
    return 0


if __name__ == "__main__":
    sys.exit(main())

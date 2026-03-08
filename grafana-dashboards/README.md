# Grafana дашборды для OpenCost

JSON-файлы в этой папке — дашборды с [Grafana.com](https://grafana.com/grafana/dashboards/) для визуализации метрик OpenCost.

| Файл | Grafana.com ID | Описание |
|------|----------------|----------|
| `opencost-overview-22208.json` | 22208 | OpenCost / Overview — сводка по кластеру (стоимость по часам/дням/месяцам, по namespace, нодам, типам инстансов) |
| `opencost-namespace-22252.json` | 22252 | OpenCost / Namespace — детализация по выбранному namespace (поды, контейнеры, PVC) |

**Импорт в Grafana:** Dashboards → New → Import → Upload JSON file → выберите файл. Укажите Data source (VictoriaMetrics или другой источник, куда скрейпятся метрики OpenCost).

Подробнее и другие варианты установки — в [README проекта](../README.md#grafana-дашборды-для-opencost).

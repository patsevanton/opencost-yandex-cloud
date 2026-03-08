# Дашборды Grafana для OpenCost (с исправлением PV)

В этой директории — дашборды с исправленной проблемой «No data» на панелях Hourly/Daily/Monthly Cost и PV.

## В чём исправление

Метрика `kube_persistentvolume_capacity_bytes` в стеке VictoriaMetrics K8s Stack приходит от **kube-state-metrics** с `job="kube-state-metrics"`, а не от OpenCost (`job="opencost"`). В оригинальных дашбордах в формулах используется `kube_persistentvolume_capacity_bytes{job=~"$job"}`, поэтому при выбранном Job = opencost запрос возвращает пустой результат и панель показывает «No data».

В исправленных дашбордах для **`kube_persistentvolume_capacity_bytes`** в фильтре указан источник метрик: **`job="kube-state-metrics"`**. Переменную **Job** в дашборде оставляйте **opencost**.

## Файлы

| Файл | Описание | Исправление |
|------|----------|-------------|
| **opencost-overview.json** | OpenCost / Overview (Grafana.com ID 22208) | Да: все формулы с PV |
| **opencost-namespace.json** | OpenCost / Namespace (Grafana.com ID 22252) | Да: формулы с PV по namespace |
| **opencost-cost-reporter-basic-overview.json** | Cost reporter — базовый обзор | Не требуется (нет запросов по PV capacity с $job) |
| **opencost-cost-reporter-detailed-overview.json** | Cost reporter — детальный обзор | Не требуется |

## Установка

1. В Grafana: **Dashboards** → **New** → **Import** → **Upload JSON file**.
2. Выберите нужный JSON из этой директории.
3. Укажите **Data source** (ваш VictoriaMetrics, например vmsingle).
4. Переменная **Job**: выберите **opencost** (или значение из метрик OpenCost).

Импорт по одному файлу; при необходимости сохраните дашборд под своим именем.

# opencost-yandex-cloud

Тестирование OpenCost в Yandex Cloud.

## Цели проекта

- **Видимость расходов** — получать расчёт стоимости Kubernetes-кластера (ноды, поды, CPU/RAM/диск) в рублях по ценам Yandex Cloud.
- **Просмотр в мониторинге** — видеть cost-метрики OpenCost в Grafana вместе с остальными метриками кластера.
- **Распределение по командам (FinOps)** — группировать расходы по лейблу `team`.
- **Сверка с биллингом** — при необходимости сравнивать аллокации OpenCost с фактическими списаниями Yandex Cloud (Billing API, детализация).
- **Доступ к cost-данным** — использовать Allocation API и метрики не только в UI/Grafana, но и через MCP для автоматизации и AI-ассистентов.

## Что такое OpenCost

OpenCost — open-source проект для расчёта и визуализации стоимости ресурсов в Kubernetes. Он агрегирует данные об использовании CPU, памяти и диска (ноды, поды, PVC), применяет к ним тарифы и даёт метрики и API для отображения затрат по namespace, deployment, label и т.д. Изначально создан в Kubecost, затем выделен в отдельный проект под CNCF; поддерживает кастомные цены и интеграцию с разными облаками и он-прем-кластерами.

## Зачем OpenCost нужен Prometheus-совместимый TSDB

OpenCost сам не собирает и не хранит метрики. Для расчёта стоимости ему нужна внешняя база временных рядов с Prometheus API, из которой он читает:

- **node-exporter** — использование CPU, памяти, диска на нодах;
- **kube-state-metrics** — запросы/лимиты подов, PVC, состояние нод.

На основе этих метрик OpenCost строит cost-модель и экспортирует свои метрики. [Подробнее →](#метрики-которые-экспортирует-opencost)


## Использование Prometheus Operator CRD

Используем Prometheus Operator CRD, чтобы не писать конфигурации скрейпинга (scrape) для vmagent вручную. CRD нужен для ServiceMonitor OpenCost: чарт OpenCost создаёт ServiceMonitor в namespace `opencost`, и vmagent (VictoriaMetrics) по нему автоматически скрейпит метрики OpenCost.

```bash
helm install prometheus-operator-crds oci://ghcr.io/prometheus-community/charts/prometheus-operator-crds --namespace kube-system --wait --version 27.0.0
```

После появления CRD в кластере чарт OpenCost сможет создать ServiceMonitor.

## Установка VictoriaMetrics Stack

```bash
helm upgrade --install --wait --timeout 10m \
    vmks oci://ghcr.io/victoriametrics/helm-charts/victoria-metrics-k8s-stack \
    --namespace vmks --create-namespace \
    --version 0.72.4 \
    --values vmks-values.yaml
```

### Пароль admin Grafana

Grafana входит в VictoriaMetrics Stack. Логин по умолчанию: `admin`. Пароль хранится в секрете Kubernetes:

```bash
kubectl get secret vmks-grafana -n vmks -o jsonpath="{.data.admin-password}" | base64 -d; echo
```

Grafana доступна по адресу http://grafana.apatsev.org.ru (см. `vmks-values.yaml`).

## Установка OpenCost

1. Создайте namespace и примените ConfigMap с кастомными ценами **до** установки OpenCost. В [issue #240](https://github.com/opencost/opencost-helm-chart/issues/240) описано, что данные в ConfigMap должны быть в виде плоских ключей в `data:`, иначе OpenCost их не прочитает:

```bash
kubectl create namespace opencost --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f custom-pricing-configmap.yaml
```

2. Установите OpenCost из OCI-репозитория:

```bash
helm upgrade --install --wait \
  opencost oci://ghcr.io/opencost/charts/opencost \
  --namespace opencost \
  --version 2.5.10 \
  --values opencost-values.yaml
```

3. После установки OpenCost будет доступен по адресу http://opencost.apatsev.org.ru. Перед использованием подождите около 10 минут — за это время OpenCost соберёт необходимые метрики из системы.

**Примечание (валюта в UI):** по умолчанию веб-интерфейс показывает USD. Переключить на RUB можно в самом UI, но при новом заходе снова будет USD — выбор не сохраняется. Валюта в UI **не** берётся из ConfigMap (ConfigMap задаёт только расчёты бэкенда); в текущих версиях OpenCost задать RUB по умолчанию через конфиг или Ingress нельзя. Чтобы сразу открывать в рублях, используйте ссылку с параметром: `http://opencost.apatsev.org.ru?currency=RUB`.

## Кастомные цены: получение и проверка данных

Тарифы для OpenCost задаются в ConfigMap `custom-pricing-model` (файл `custom-pricing-configmap.yaml`). Для полей CPU, RAM и storage указываются **месячные** ставки (₽/мес за единицу); OpenCost переводит их в почасовые делением на 730.

### Автоматическое обновление ConfigMap из Billing API

Скрипт `scripts/fetch_yandex_sku_prices.py` запрашивает тарифы через Sku.List, подбирает SKU для vCPU, RAM, диска и исходящего трафика и может обновить `custom-pricing-configmap.yaml`:

```bash
export IAM_TOKEN=$(yc iam create-token)
# Показать подобранные цены (рубли), не менять файлы:
python3 scripts/fetch_yandex_sku_prices.py

# Обновить custom-pricing-configmap.yaml:
python3 scripts/fetch_yandex_sku_prices.py --update custom-pricing-configmap.yaml
```

Токен можно не задавать, если установлен CLI `yc` — скрипт вызовет `yc iam create-token`. После обновления ConfigMap запустите валидацию и при необходимости примените манифест в кластер. Подробнее: [custom-pricing-strategy.md](custom-pricing-strategy.md).

## Стоимость по командам (team cost)

OpenCost позволяет группировать расходы по командам, даже если у команды несколько namespace. Для этого используется агрегация по Kubernetes-лейблу через параметр `aggregate=label:<имя_лейбла>`.

### Настройка

Label, по которому будет групировка, в этом проекте (`team`), должен быть установлен **на самом Pod**. Установка лейбла только на объект `Deployment` / `StatefulSet` / `DaemonSet` (в их `metadata.labels`) или только на `Namespace` **не позволяет** группировать расходы по командам — OpenCost учитывает только лейблы на подах.

В этом проекте уже настроены лейблы для группировки инфраструктурных затрат:
- **Victoria Metrics K8s Stack** (`vmks-values.yaml`): поды vmsingle, vmagent, vmalert, alertmanager, grafana, node-exporter, kube-state-metrics и victoria-metrics-operator помечены `team: metrics` (через `spec.podMetadata.labels` для CR-компонентов и `podLabels` для подчартов).
- **OpenCost** (`opencost-values.yaml`): под OpenCost помечен `team: finops`.

### Агрегация в UI

В веб-интерфейсе OpenCost есть выпадающий список **«Aggregate by»** (Namespace, Deployment, Pod и т.д.). Варианта «по лейблу team» в стандартной сборке может не быть — его можно открыть **через URL**, добавив параметр `agg=label:team`:

<http://opencost.apatsev.org.ru/allocation?window=today&agg=label:team&acc=true>

Так откроется отчёт за 7 дней, сгруппированный по командам (включая `metrics` и `finops`). Важно: в URL веб-интерфейса используется параметр `agg`, а в API и MCP для той же логики используется `aggregate=label:team`.

## Скрейпинг метрик OpenCost

OpenCost не только читает метрики из VictoriaMetrics, но и **отдаёт свои** (`node_cpu_hourly_cost`, `container_cpu_allocation` и др.) на порту 9003 (`/metrics`). `ServiceMonitor` сам метрики не создаёт, а лишь описывает для `vmagent`, как их скрейпить. Эти метрики должны попадать в VictoriaMetrics; иначе в TSDB не будет cost-метрик, и Grafana/PromQL-запросы к ним будут возвращать `No data`.

### Дублирование метрик kube_* и опции EMIT_KSM_V1_*

Эндпоинт OpenCost `/metrics` по умолчанию отдаёт те же метрики, что и **kube-state-metrics** (`kube_pod_container_status_running`, `kube_pod_container_resource_requests`, `kube_node_status_*` и др.). Если vmagent скрейпит и OpenCost, и kube-state-metrics, в VictoriaMetrics одни и те же ряды попадают из двух источников — запросы вида `sum(kube_pod_container_status_running)` дают **удвоенные** значения. Удвоенные значения вредны: искажают дашборды, агрегаты и любые расчёты, опирающиеся на эти метрики. Подробнее: [opencost/opencost#1465](https://github.com/opencost/opencost/issues/1465).

В этом проекте предполагается, что **kube-state-metrics всегда есть** (он входит в VictoriaMetrics K8s Stack). Ниже — опции в `opencost-values.yaml`, которые отключают дубликаты.

#### Отключение дубликатов KSM в opencost-values.yaml

В `opencost-values.yaml` заданы:

| Переменная | Значение | Смысл |
|------------|----------|--------|
| `EMIT_KSM_V1_METRICS` | `"false"` | Не отдавать полный набор KSM-метрик на `/metrics`. |
| `EMIT_KSM_V1_METRICS_ONLY` | `"true"` | Отдаются метрики, которые не пересекаются по имени и не дублируются с kube-state-metrics. |

## Дашборды Grafana для OpenCost

Ниже приведены ссылки на четыре переработанных дашборда:

| Файл | GitHub | Описание |
|------|--------|----------|
| **opencost-overview.json** | [ссылка](https://github.com/patsevanton/opencost-yandex-cloud/blob/main/grafana-dashboards/opencost-overview.json) | OpenCost / Overview (Grafana.com ID 22208) |
| **opencost-namespace.json** | [ссылка](https://github.com/patsevanton/opencost-yandex-cloud/blob/main/grafana-dashboards/opencost-namespace.json) | OpenCost / Namespace (Grafana.com ID 22252) |
| **opencost-cost-reporter-basic-overview.json** | [ссылка](https://github.com/patsevanton/opencost-yandex-cloud/blob/main/grafana-dashboards/opencost-cost-reporter-basic-overview.json) | Cost reporter - базовый обзор |
| **opencost-cost-reporter-detailed-overview.json** | [ссылка](https://github.com/patsevanton/opencost-yandex-cloud/blob/main/grafana-dashboards/opencost-cost-reporter-detailed-overview.json) | Cost reporter - детальный обзор |

### Суть исправлений

Проблема `No data` возникала в дашбордах `opencost-overview.json` и `opencost-namespace.json` на панелях Hourly/Daily/Monthly Cost и PV. Метрика `kube_persistentvolume_capacity_bytes` в VictoriaMetrics K8s Stack приходит от `kube-state-metrics` с `job="kube-state-metrics"`, а не от OpenCost с `job="opencost"`. В оригинальных дашбордах использовался фильтр `kube_persistentvolume_capacity_bytes{job=~"$job"}`, поэтому при выбранном `Job = opencost` запрос возвращал пустой результат.

В исправленных дашбордах для `kube_persistentvolume_capacity_bytes` в фильтре указан источник `job="kube-state-metrics"`. Дашборды `opencost-cost-reporter-basic-overview.json` и `opencost-cost-reporter-detailed-overview.json` этой правки не требовали. Переменную `Job` в дашборде оставляйте `opencost`.

### Валюта в панелях

Дашборды по умолчанию показывают единицу **currencyUSD**. При кастомных ценах в рублях (RUB) числовые значения в метриках уже в рублях; подпись единицы в панели при необходимости можно изменить в настройках панели (Field → Unit).

## Метрики, которые экспортирует OpenCost

Запросы за прошлые периоды (день, месяц) выполняются через PromQL по уже сохранённым данным в TSDB. Без Prometheus-совместимого хранилища OpenCost не из чего считать стоимость. В этом репозитории в качестве TSDB используется VictoriaMetrics (совместима с Prometheus API).

OpenCost отдаёт метрики на порту **9003** (`/metrics`). Ниже — группы **cost-метрик** (исключая стандартные `go_*`, `process_*`, `promhttp_*` и дубликаты kube-state-metrics). При кастомных ценах в рублях (`currency: RUB`) значения cost-метрик — в **₽/час**, а не в USD/час.

В репозитории четыре дашборда: **OpenCost Overview**, **OpenCost Namespace**, **OpenCost Cost reporter / Basic overview**, **OpenCost Cost reporter / Detailed overview**.

| Метрика | Описание | Лейблы | Единица | Дашборд / панель |
|--------|----------|--------|--------|------------------|
| **Стоимость нод** | | | | |
| `node_cpu_hourly_cost` | Часовая стоимость за 1 vCPU | node, instance, provider_id | ₽/час (при RUB) | **Overview:** Hourly/Daily/Monthly Cost, Monthly CPU Cost, Cost by Namespace, Cost by Instance Type, Nodes Monthly Cost, Namespace Summary, Namespace Monthly Cost. **Namespace:** Hourly/Daily/Monthly Cost, Monthly CPU/Ram, Cost by Resource, Pod/Container Summary, Cost by Pod/Container. **Basic:** Average Daily, Cluster Hour Cost, Estimative Monthly, Top 20 Namespaces/Containers/Pods, Hour Cost by Namespace/Container, By Namespace, Estimated monthly/daily/hourly. **Detailed:** Top 20 by Namespace/Container, Hour Cost, Live Month/Day/Hour Price, Hour Price by App, App by pod, APP Hour Price, APP Pods Hour Price. |
| `node_gpu_hourly_cost` | Часовая стоимость за 1 GPU | node, instance, provider_id | ₽/час (при RUB) | — |
| `node_ram_hourly_cost` | Часовая стоимость за 1 GiB RAM | node, instance, provider_id | ₽/час (при RUB) | Те же панели, что и `node_cpu_hourly_cost` (в формулах стоимости по CPU+RAM). |
| `node_total_hourly_cost` | Полная часовая стоимость ноды | node, instance, provider_id | ₽/час (при RUB) | **Overview:** Hourly/Daily/Monthly Cost, Cost by Instance Type, Nodes Monthly Cost. **Basic:** Average Daily Cloud Costs, Cluster Hour Cost, Estimative Monthly, Relative price, Standard Variation. **Detailed:** AVG Cluster Cost, Cluster Hour Price, Estimative Cluster Cost, Relative price, Standard Variation. |
| `node_gpu_count` | Количество GPU на ноде | node, instance, provider_id | шт. | — |
| `kubecost_node_is_spot` | Нода прерываемая (spot) или нет | node, instance, provider_id | 0/1 | — |
| **Аллокации (контейнеры/поды)** | | | | |
| `container_cpu_allocation` | Аллокация CPU за последнюю 1 мин | container, node, namespace, pod | ядра | **Overview:** Cost by Namespace, Namespace Summary, Namespace Monthly Cost. **Namespace:** все панели стоимости по namespace/pod/container. **Basic:** Estimated Top 20 Namespaces/Containers/Pods, Hour Cost by Namespace/Container, By Namespace. **Detailed:** Top 20 by Namespace/Container, Hour Cost, Live Month/Day/Hour Price, Hour Price by App, App by pod, APP Hour Price, APP Pods Hour Price. |
| `container_gpu_allocation` | Аллокация GPU за последнюю 1 мин | container, node, namespace, pod | шт. | — |
| `container_memory_allocation_bytes` | Аллокация памяти за последнюю 1 мин | container, node, namespace, pod | байты | Те же панели, что и `container_cpu_allocation`. |
| `pod_pvc_allocation` | Аллокация PVC по поду | persistentvolume, namespace, pod | байты | — |
| **Сеть** | | | | |
| `kubecost_network_zone_egress_cost` | Стоимость за GiB egress в зоне | namespace, service | ₽/GiB (при RUB) | — |
| `kubecost_network_region_egress_cost` | Стоимость за GiB egress в регионе | namespace, service | ₽/GiB (при RUB) | — |
| `kubecost_network_internet_egress_cost` | Стоимость за GiB egress в интернет | namespace, service | ₽/GiB (при RUB) | — |
| `kubecost_network_nat_gateway_egress_cost` | Стоимость egress через NAT Gateway | namespace, service | ₽/GiB (при RUB) | — |
| `kubecost_network_nat_gateway_ingress_cost` | Стоимость ingress через NAT Gateway | namespace, service | ₽/GiB (при RUB) | — |
| **Хранилище и LB** | | | | |
| `pv_hourly_cost` | Часовая стоимость за 1 GiB PV | persistentvolume | ₽/час (при RUB) | **Overview:** Hourly/Daily/Monthly Cost, Monthly PV Cost, Cost by Resource, Persistent Volumes Monthly Cost. **Namespace:** Monthly PV Cost, PV Summary, Persistent Volumes Monthly Cost, Cost by PV. **Detailed:** Kubernetes EBS allocation price by day, PVCs (AWS EBS). |
| `kubecost_load_balancer_cost` | Часовая стоимость Load Balancer | namespace, service | ₽/час (при RUB) | — |
| **Кластер** | | | | |
| `kubecost_cluster_management_cost` | Часовая плата за управление кластером | cluster | ₽/час (при RUB) | — |
| `kubecost_cluster_info` | Информация о кластере | cluster, provider | info | — |
| **Лейблы (для маппинга)** | | | | |
| `service_selector_labels` | Селекторы сервисов | namespace, service | лейблы | — |
| `deployment_match_labels` | Match-лейблы deployment | namespace, deployment | лейблы | — |
| `statefulSet_match_labels` | Match-лейблы StatefulSet | namespace, statefulset | лейблы | — |
| **Внутренние/операционные** | | | | |
| `kubecost_http_requests_total` | Число HTTP-запросов | endpoint, method, status | счётчик | — |
| `kubecost_http_response_time_seconds` | Время ответа | endpoint, method | сек | — |
| `kubecost_http_response_size_bytes` | Размер ответа | endpoint, method | байты | — |

Примеры PromQL: месячная стоимость всех нод — `sum(node_total_hourly_cost) * 730`; стоимость CPU+RAM по namespace — см. [документацию OpenCost](https://opencost.io/docs/integrations/metrics/).

Подключение OpenCost через MCP (для AI-ассистентов) описано в [mcp.md](mcp.md).


# Биллинг Yandex Cloud и интеграция с OpenCost

## Cloud Costs и External Costs в OpenCost

OpenCost помимо расчёта стоимости Kubernetes (Allocation API) предоставляет два дополнительных механизма:

| Механизм | Появился | Что учитывает |
|----------|----------|---------------|
| **Cloud Costs** | 1.108.0 | Фактические расходы из billing API облачного провайдера (AWS, GCP, Azure). Показывает реальные списания, а не расчёт по list price. |
| **External Costs** | 1.110.0 | Затраты на сторонние сервисы вне облака: мониторинг (Datadog), SaaS (MongoDB Atlas), AI/API (OpenAI) и т.п. |

**Yandex Cloud** не входит в список поддерживаемых провайдеров Cloud Costs. External Costs не подходит, так как нас интересуют расходы на само облако, а не на сторонние сервисы.

## Yandex Cloud Billing API: почему не поможет с детализацией

Billing API v1 (gRPC/REST) содержит три сервиса:

| Сервис | Что даёт |
|--------|----------|
| `BillingAccountService` | Список аккаунтов, баланс, привязки |
| `SkuService` | Каталог SKU и тарифы (list price) |
| `ServiceService` | Справочник сервисов |

**Ни один из них не предоставляет фактического потребления или списаний.** Нельзя запросить «сколько потрачено за период X на сервис Y» — API отдаёт только баланс, тарифы и список сервисов. Детализация расходов доступна только через экспорт в CSV.

## Доступные способы получения фактических расходов Yandex Cloud

### CSV-экспорт в Object Storage

Источник: [Экспортировать расширенную детализацию](https://yandex.cloud/ru/docs/billing/operations/get-folder-report).

- **Разовый экспорт** — в консоли биллинга выгрузка за выбранный период в CSV.
- **Регулярный экспорт** — в настройках биллинга задаётся бакет Object Storage, куда ежедневно выгружаются CSV (обновление раз в час). Поресурсная детализация включает `resource_id`, `sku_id`, идентификаторы каталогов, лейблы.

Для программного доступа: настроить экспорт в бакет и читать CSV через S3-совместимый API.

### Yandex Query

Если детализация уже выгружается в бакет, можно анализировать данные через [Yandex Query](https://yandex.cloud/ru-kz/docs/billing/operations/query-integration): готовые запросы (топ ресурсов, расход по сервисам) и произвольный YQL. Результаты доступны через HTTP API.

## Возможные пути интеграции с OpenCost

| Путь | Тип в OpenCost | Описание |
|------|----------------|----------|
| Кастомный Cloud Costs провайдер | Cloud Costs (`/cloudCost`) | Go-код в ядро OpenCost, читающий CSV из Object Storage (S3-совместимый API). Аналог интеграций AWS (CUR из S3) и Azure (Cost Exports). Требует модификации ядра. |
| OpenCost Plugin | External Costs (`/customCost/*`) | Плагин, читающий CSV из Object Storage или вызывающий Yandex Query HTTP API. Не требует модификации ядра OpenCost. Репозиторий: [opencost-plugins](https://github.com/opencost/opencost-plugins). |

**Итог:** прямого API для получения списаний у Yandex Cloud нет — фактические расходы доступны только через CSV-экспорт в Object Storage. Наиболее реалистичный путь интеграции — **OpenCost Plugin**, читающий CSV-детализацию из Object Storage через S3-совместимый API.
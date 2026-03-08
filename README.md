# opencost-yandex-cloud

Тестирование OpenCost в Yandex Cloud.

## Цели проекта

- **Видимость расходов** — получать расчёт стоимости Kubernetes-кластера (ноды, поды, CPU/RAM/диск) в рублях по ценам Yandex Cloud.
- **Просмотр в мониторинге** — видеть cost-метрики OpenCost в Grafana вместе с остальными метриками кластера.
- **Распределение по командам (FinOps)** — группировать расходы по лейблу `team` (chargeback/showback), в том числе для инфраструктурных компонентов (metrics, finops).
- **Сверка с биллингом** — при необходимости сравнивать аллокации OpenCost с фактическими списаниями Yandex Cloud (Billing API, детализация).
- **Доступ к cost-данным** — использовать Allocation API и метрики не только в UI/Grafana, но и через MCP для автоматизации и AI-ассистентов.

## Что такое OpenCost

OpenCost — open-source проект для расчёта и визуализации стоимости ресурсов в Kubernetes. Он агрегирует данные об использовании CPU, памяти и диска (ноды, поды, PVC), применяет к ним тарифы и даёт метрики и API для отображения затрат по namespace, deployment, label и т.д. Изначально создан в Kubecost, затем выделен в отдельный проект под CNCF; поддерживает кастомные цены и интеграцию с разными облаками и онпрем-кластерами.

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

Дашборды с Grafana.com по умолчанию показывают единицу **currencyUSD**. При кастомных ценах в рублях (RUB) числовые значения в метриках уже в рублях; подпись единицы в панели при необходимости можно изменить в настройках панели (Field → Unit).

## Кастомные цены: получение и проверка данных

Тарифы для OpenCost задаются в ConfigMap `custom-pricing-model` (файл `custom-pricing-configmap.yaml`). Для полей CPU, RAM и storage указываются **месячные** ставки (₽/мес за единицу); OpenCost переводит их в почасовые делением на 730.

### Валюта (Currency)

Все цены в ConfigMap заданы в **рублях (₽)**. В `custom-pricing-configmap.yaml` указано `currency: "RUB"` — бэкенд OpenCost использует это для расчётов и метрик. В веб-интерфейсе OpenCost валюта отображения **не** берётся из ConfigMap: UI по умолчанию подставляет USD, если в URL нет query-параметра `currency`. Чтобы в UI по умолчанию показывалось **RUB**, в `opencost-values.yaml` для UI Ingress включён редирект: при заходе без `currency` в URL запрос перенаправляется на тот же путь с `currency=RUB`. Тогда подпись валюты в интерфейсе совпадает с рублёвыми значениями из custom pricing.

### Откуда брать значения

| Источник | Описание |
|----------|----------|
| **Документация Yandex Cloud** | [Тарификация Compute Cloud](https://cloud.yandex.ru/docs/compute/pricing) — почасовые цены vCPU, RAM, диск, трафик. Месячная ставка = почасовая × 730. Регион и тип диска — по вашему кластеру. |
| **Billing API (SkuService)** | Методы [Sku.List](https://yandex.cloud/ru/docs/billing/api-ref/Sku/list) возвращают каталог SKU и list price. Нужен IAM-токен; маппинг SKU → vCPU/RAM/диск и пересчёт в формат ConfigMap можно автоматизировать скриптом. |
| **Вручную** | Закрепить в комментариях ConfigMap формулу (например `# 1.2852 ₽/vCPU-час * 730`) и ссылку на страницу тарификации — при следующем обновлении расчёт повторить легко. |

### Как проверять

1. **Локально (перед применением)** — скрипт проверяет наличие обязательных ключей и что числовые значения в разумных диапазонах:
   ```bash
   python3 scripts/validate_custom_pricing.py --file custom-pricing-configmap.yaml
   ```
   Проверка ConfigMap из кластера: `kubectl get configmap custom-pricing-model -n opencost -o yaml | python3 scripts/validate_custom_pricing.py --stdin`

2. **В кластере** — после `kubectl apply` при необходимости перезапустить под OpenCost; убедиться в UI или по метрикам (`node_cpu_hourly_cost`, `node_total_hourly_cost`), что стоимость нод и аллокаций не нулевая и не аномальная.

3. **Сверка с биллингом** — за выбранный период сравнить сумму из Allocation API с фактическими списаниями (экспорт детализации в Object Storage или Yandex Query). Подробнее: [yandex-cloud-billing-api-charges.md](yandex-cloud-billing-api-charges.md).

### Чек-лист обновления тарифов

1. Взять актуальные почасовые цены из [тарификации](https://cloud.yandex.ru/docs/compute/pricing) (ваш регион).  
2. Посчитать месячные: vCPU/RAM/диск × 730.  
3. Обновить `custom-pricing-configmap.yaml`, оставить комментарии с формулой.  
4. Запустить `scripts/validate_custom_pricing.py --file custom-pricing-configmap.yaml`.  
5. Применить ConfigMap, при необходимости перезапустить OpenCost.  
6. Проверить метрики/UI и при возможности сверить с биллингом.

Подробное описание полей ConfigMap, источников и проверок — в [custom-pricing-strategy.md](custom-pricing-strategy.md).

## Стоимость по командам (team cost)

OpenCost позволяет группировать расходы по командам, даже если у команды несколько namespace. Для этого используется агрегация по Kubernetes-лейблу через параметр `aggregate=label:<имя_лейбла>`.

### Настройка

**1. Добавьте лейбл `team` на workload-ресурсы** (pods, deployments, daemonsets) во всех namespace команды:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: team-a-backend
spec:
  template:
    metadata:
      labels:
        team: team-a
```

> **Важно:** лейблы должны стоять на **workload-ресурсах**, то есть в `spec.template.metadata.labels` у `Deployment` / `StatefulSet` / `DaemonSet`, чтобы они попадали на Pod'ы, а **не на самих namespace**. Если повесить `team` только на объект `Namespace`, агрегация не сработает корректно: OpenCost не использует namespace-лейблы для аллокаций и в таком сценарии вернёт стоимость всего кластера ([issue #2753](https://github.com/opencost/opencost/issues/2753)).

В этом репозитории уже настроены лейблы для группировки инфраструктурных затрат:
- **Victoria Metrics K8s Stack** (`vmks-values.yaml`): поды vmsingle, vmagent, vmalert, alertmanager, grafana, node-exporter, kube-state-metrics и victoria-metrics-operator помечены `team: metrics` (через `spec.podMetadata.labels` для CR-компонентов и `podLabels` для подчартов).
- **OpenCost** (`opencost-values.yaml`): под OpenCost помечен `team: finops`.

**2. Агрегация в UI**

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

## Метрики, которые экспортирует OpenCost

Запросы за прошлые периоды (день, месяц) выполняются через PromQL по уже сохранённым данным в TSDB. Без Prometheus-совместимого хранилища OpenCost не из чего считать стоимость. В этом репозитории в качестве TSDB используется VictoriaMetrics (совместима с Prometheus API).

OpenCost отдаёт метрики на порту **9003** (`/metrics`). Ниже — группы **cost-метрик** (исключая стандартные `go_*`, `process_*`, `promhttp_*` и дубликаты kube-state-metrics). При кастомных ценах в рублях (`currency: RUB`) значения cost-метрик — в **₽/час**, а не в USD/час.

| Метрика | Описание | Лейблы | Единица |
|--------|----------|--------|--------|
| **Стоимость нод** | | | |
| `node_cpu_hourly_cost` | Часовая стоимость за 1 vCPU | node, instance, provider_id | ₽/час (при RUB) |
| `node_gpu_hourly_cost` | Часовая стоимость за 1 GPU | node, instance, provider_id | ₽/час (при RUB) |
| `node_ram_hourly_cost` | Часовая стоимость за 1 GiB RAM | node, instance, provider_id | ₽/час (при RUB) |
| `node_total_hourly_cost` | Полная часовая стоимость ноды | node, instance, provider_id | ₽/час (при RUB) |
| `node_gpu_count` | Количество GPU на ноде | node, instance, provider_id | шт. |
| `kubecost_node_is_spot` | Нода прерываемая (spot) или нет | node, instance, provider_id | 0/1 |
| **Аллокации (контейнеры/поды)** | | | |
| `container_cpu_allocation` | Аллокация CPU за последнюю 1 мин | container, node, namespace, pod | ядра |
| `container_gpu_allocation` | Аллокация GPU за последнюю 1 мин | container, node, namespace, pod | шт. |
| `container_memory_allocation_bytes` | Аллокация памяти за последнюю 1 мин | container, node, namespace, pod | байты |
| `pod_pvc_allocation` | Аллокация PVC по поду | persistentvolume, namespace, pod | байты |
| **Сеть** | | | |
| `kubecost_network_zone_egress_cost` | Стоимость за GiB egress в зоне | namespace, service | ₽/GiB (при RUB) |
| `kubecost_network_region_egress_cost` | Стоимость за GiB egress в регионе | namespace, service | ₽/GiB (при RUB) |
| `kubecost_network_internet_egress_cost` | Стоимость за GiB egress в интернет | namespace, service | ₽/GiB (при RUB) |
| `kubecost_network_nat_gateway_egress_cost` | Стоимость egress через NAT Gateway | namespace, service | ₽/GiB (при RUB) |
| `kubecost_network_nat_gateway_ingress_cost` | Стоимость ingress через NAT Gateway | namespace, service | ₽/GiB (при RUB) |
| **Хранилище и LB** | | | |
| `pv_hourly_cost` | Часовая стоимость за 1 GiB PV | persistentvolume | ₽/час (при RUB) |
| `kubecost_load_balancer_cost` | Часовая стоимость Load Balancer | namespace, service | ₽/час (при RUB) |
| **Кластер** | | | |
| `kubecost_cluster_management_cost` | Часовая плата за управление кластером | cluster | ₽/час (при RUB) |
| `kubecost_cluster_info` | Информация о кластере | cluster, provider | info |
| **Лейблы (для маппинга)** | | | |
| `service_selector_labels` | Селекторы сервисов | namespace, service | лейблы |
| `deployment_match_labels` | Match-лейблы deployment | namespace, deployment | лейблы |
| `statefulSet_match_labels` | Match-лейблы StatefulSet | namespace, statefulset | лейблы |
| **Внутренние/операционные** | | | |
| `kubecost_http_requests_total` | Число HTTP-запросов | endpoint, method, status | счётчик |
| `kubecost_http_response_time_seconds` | Время ответа | endpoint, method | сек |
| `kubecost_http_response_size_bytes` | Размер ответа | endpoint, method | байты |

Примеры PromQL: месячная стоимость всех нод — `sum(node_total_hourly_cost) * 730`; стоимость CPU+RAM по namespace — см. [документацию OpenCost](https://opencost.io/docs/integrations/metrics/).

Подключение OpenCost через MCP (для AI-ассистентов) описано в [mcp.md](mcp.md).
# opencost-yandex-cloud

Тестирование OpenCost в Yandex Cloud.

## Цели проекта

- **Видимость расходов** — получать расчёт стоимости Kubernetes-кластера (ноды, поды, CPU/RAM/диск) в рублях по ценам Yandex Cloud.
- **Стек на базе VictoriaMetrics** — использовать VictoriaMetrics как Prometheus-совместимую TSDB для OpenCost вместо отдельного Prometheus.
- **Кастомные цены** — задавать тарифы через ConfigMap и обходить ограничения Helm-чарта OpenCost в формате цен.
- **Интеграция с мониторингом** — скрейпить cost-метрики OpenCost в VictoriaMetrics и смотреть их в Grafana.

## TODO

- [ ] Проверить через curl (или другие инструменты) получение детализации расходов по API Yandex Cloud: [Получение детализации через API](https://yandex.cloud/ru/docs/billing/operations/get-charges-via-api).

Все Helm-чарты в инструкциях ниже устанавливаются через **OCI** (`oci://...`), без `helm repo add`.

## Что такое OpenCost

OpenCost — open-source проект для расчёта и визуализации стоимости ресурсов в Kubernetes. Он агрегирует данные об использовании CPU, памяти и диска (ноды, поды, PVC), применяет к ним тарифы и даёт метрики и API для отображения затрат по namespace, deployment, label и т.д. Изначально создан в Kubecost, затем выделен в отдельный проект под CNCF; поддерживает кастомные цены и интеграцию с разными облаками и онпрем-кластерами.

## Зачем OpenCost нужен Prometheus-совместимый TSDB

OpenCost сам не собирает и не хранит метрики. Для расчёта стоимости ему нужна внешняя база временных рядов с Prometheus API, из которой он читает:

- **node-exporter** — использование CPU, памяти, диска на нодах;
- **kube-state-metrics** — запросы/лимиты подов, PVC, состояние нод.

На основе этих метрик OpenCost строит cost-модель и экспортирует свои метрики. [Подробнее →](#метрики-которые-экспортирует-opencost)

## Prometheus Operator CRD

Prometheus Operator CRD нужен для ServiceMonitor OpenCost: чарт OpenCost создаёт ServiceMonitor в namespace `opencost`, чтобы vmagent (VictoriaMetrics) скрейпил метрики OpenCost.

```bash
helm install prometheus-operator-crds oci://ghcr.io/prometheus-community/charts/prometheus-operator-crds --namespace kube-system --wait --version 27.0.0
```

После появления CRD в кластере чарт OpenCost сможет создать ServiceMonitor.

## Установка VictoriaMetrics Stack

Установка через OCI (без `helm repo add`):

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

Установка через OCI (без `helm repo add`):

1. Создайте namespace и примените ConfigMap с кастомными ценами **до** установки OpenCost. В [issue #240](https://github.com/opencost/opencost-helm-chart/issues/240) описано, что данные в ConfigMap должны быть в виде плоских ключей в `data:`, иначе OpenCost их не прочитает.
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

> **Важно:** лейблы должны стоять на **workload-ресурсах** (pod template - уточнить), а **не на самих namespace**. Если повесить `team` только на объект Namespace, агрегация не сработает корректно — OpenCost вернёт стоимость всего кластера ([issue #2753](https://github.com/opencost/opencost/issues/2753)). Навесить label на Namespace и считать по нему без лейблов на pod/Deployment **нельзя**: OpenCost не использует лейблы namespace для аллокаций.

**2. Запросите стоимость через API:**

```bash
curl -G http://opencost.apatsev.org.ru/allocation  \
  -d window=7d \
  -d aggregate=label:team \
  -d accumulate=true
```

Результат — общая стоимость за 7 дней, сгруппированная по значению лейбла `team`, независимо от namespace.

В этом репозитории уже настроены лейблы для группировки инфраструктурных затрат:
- **Victoria Metrics K8s Stack** (`vmks-values.yaml`): поды vmsingle и vmagent помечены `team: metrics`.
- **OpenCost** (`opencost-values.yaml`): под OpenCost помечен `team: finops`.

**3. Агрегация в UI**

В веб-интерфейсе OpenCost (порт 9090) есть выпадающий список **«Aggregate by»** (Namespace, Deployment, Pod и т.д.). Варианта «по лейблу team» в стандартной сборке может не быть — его можно открыть **через URL**, добавив параметр `agg=label:team`:

```
http://opencost.apatsev.org.ru/allocation?window=7d&agg=label:team&acc=true
```

Так откроется отчёт за 7 дней, сгруппированный по командам (включая `metrics` и `finops`). Через API и MCP агрегация `aggregate=label:team` доступна без ограничений.

## Скрейпинг метрик OpenCost

OpenCost не только читает метрики из VictoriaMetrics, но и **отдаёт свои** (`node_cpu_hourly_cost`, `container_cpu_allocation` и др.) через **активацию ServiceMonitor** — на порту 9003 (`/metrics`). Эти метрики должны **скрейпиться vmagent'ом** и попадать в VictoriaMetrics; иначе в TSDB нет cost-метрик и в UI отображается «No results».

## Метрики, которые экспортирует OpenCost

Запросы за прошлые периоды (день, месяц) выполняются через PromQL по уже сохранённым данным в TSDB. Без Prometheus-совместимого хранилища OpenCost не из чего считать стоимость. В этом репозитории в качестве TSDB используется VictoriaMetrics (совместима с Prometheus API).

OpenCost отдаёт метрики на порту **9003** (`/metrics`). Ниже — группы **cost-метрик** (исключая стандартные `go_*`, `process_*`, `promhttp_*` и дубликаты kube-state-metrics).

| Метрика | Описание | Лейблы | Единица |
|--------|----------|--------|--------|
| **Стоимость нод** | | | |
| `node_cpu_hourly_cost` | Часовая стоимость за 1 vCPU | node, instance, provider_id | USD/час |
| `node_gpu_hourly_cost` | Часовая стоимость за 1 GPU | node, instance, provider_id | USD/час |
| `node_ram_hourly_cost` | Часовая стоимость за 1 GiB RAM | node, instance, provider_id | USD/час |
| `node_total_hourly_cost` | Полная часовая стоимость ноды | node, instance, provider_id | USD/час |
| `node_gpu_count` | Количество GPU на ноде | node, instance, provider_id | шт. |
| `kubecost_node_is_spot` | Нода прерываемая (spot) или нет | node, instance, provider_id | 0/1 |
| **Аллокации (контейнеры/поды)** | | | |
| `container_cpu_allocation` | Аллокация CPU за последнюю 1 мин | container, node, namespace, pod | ядра |
| `container_gpu_allocation` | Аллокация GPU за последнюю 1 мин | container, node, namespace, pod | шт. |
| `container_memory_allocation_bytes` | Аллокация памяти за последнюю 1 мин | container, node, namespace, pod | байты |
| `pod_pvc_allocation` | Аллокация PVC по поду | persistentvolume, namespace, pod | байты |
| **Сеть** | | | |
| `kubecost_network_zone_egress_cost` | Стоимость за GiB egress в зоне | namespace, service | USD/GiB |
| `kubecost_network_region_egress_cost` | Стоимость за GiB egress в регионе | namespace, service | USD/GiB |
| `kubecost_network_internet_egress_cost` | Стоимость за GiB egress в интернет | namespace, service | USD/GiB |
| `kubecost_network_nat_gateway_egress_cost` | Стоимость egress через NAT Gateway | namespace, service | USD/GiB |
| `kubecost_network_nat_gateway_ingress_cost` | Стоимость ingress через NAT Gateway | namespace, service | USD/GiB |
| **Хранилище и LB** | | | |
| `pv_hourly_cost` | Часовая стоимость за 1 GiB PV | persistentvolume | USD/час |
| `kubecost_load_balancer_cost` | Часовая стоимость Load Balancer | namespace, service | USD/час |
| **Кластер** | | | |
| `kubecost_cluster_management_cost` | Часовая плата за управление кластером | cluster | USD/час |
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

### Получение метрик через kubectl

Метрики отдаются на порту **9003**, путь `/metrics`. Варианты:

**1. Port-forward и curl (удобно для просмотра локально):**
```bash
# В одном терминале — поднять туннель
kubectl port-forward -n opencost svc/opencost 9003:9003

# В другом — только названия метрик (без значений и комментариев)
curl -s http://localhost:9003/metrics | grep -v '^#' | awk '{print $1}' | sed 's/{.*//' | grep . | sort -u > opencost_metrics.txt
```

**2. Сравнение метрик из файла с VictoriaMetrics (внутри кластера):**

```bash
# Терминал 1 — туннель к VictoriaMetrics
kubectl port-forward -n vmks svc/vmsingle-vmks-victoria-metrics-k8s-stack 8428:8428

# Терминал 2 — из корня репозитория
python3 scripts/compare_vm_metrics.py \
  --vm-url http://localhost:8428 \
  --file opencost_metrics.txt
```

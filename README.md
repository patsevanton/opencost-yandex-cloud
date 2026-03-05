# opencost-yandex-cloud

Тестирование OpenCost в Yandex Cloud.

## Цели проекта

- **Видимость расходов** — получать расчёт стоимости Kubernetes-кластера (ноды, поды, CPU/RAM/диск) в рублях по ценам Yandex Cloud.
- **Стек на базе VictoriaMetrics** — использовать VictoriaMetrics как Prometheus-совместимую TSDB для OpenCost вместо отдельного Prometheus.
- **Кастомные цены** — задавать тарифы через ConfigMap и обходить ограничения Helm-чарта OpenCost в формате цен.
- **Интеграция с мониторингом** — скрейпить cost-метрики OpenCost в VictoriaMetrics и смотреть их в Grafana.
- **MCP для AI-ассистентов** — подключать OpenCost по MCP (Cursor и др.) для запросов о стоимости через естественный язык.

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

Для установки VictoriaMetrics Stack в кластер Kubernetes выполните следующие шаги:

1. Добавьте репозиторий Helm-чартов VictoriaMetrics:
```bash
helm repo add vm https://victoriametrics.github.io/helm-charts/
helm repo update
```

2. Установите VictoriaMetrics Stack с включённым Ingress:
```bash
helm upgrade --install --wait --timeout 10m \
      vmks vm/victoria-metrics-k8s-stack \
      --namespace vmks --create-namespace \
      --version 0.72.2 \
      --values vmks-values.yaml
```

### Пароль admin Grafana

Grafana входит в VictoriaMetrics Stack. Логин по умолчанию: `admin`. Пароль хранится в секрете Kubernetes:

```bash
kubectl get secret vmks-grafana -n vmks -o jsonpath="{.data.admin-password}" | base64 -d; echo
```

Grafana доступна по адресу http://grafana.apatsev.org.ru (см. `vmks-values.yaml`).

## Установка OpenCost

Для установки OpenCost в кластер Kubernetes выполните следующие шаги:

1. Добавьте репозиторий OpenCost Helm:
```bash
helm repo add opencost https://opencost.github.io/opencost-helm-chart
helm repo update
```

2. Создайте namespace и примените ConfigMap с кастомными ценами **до** установки OpenCost. В [issue #240](https://github.com/opencost/opencost-helm-chart/issues/240) описано, что данные в ConfigMap должны быть в виде плоских ключей в `data:`, иначе OpenCost их не прочитает.
```bash
kubectl create namespace opencost --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f custom-pricing-configmap.yaml
```

3. Установите OpenCost, используя подготовленный файл значений:
```bash
helm upgrade --install --wait \
   opencost opencost/opencost \
   --namespace opencost \
   --version 2.5.9 \
   --values opencost-values.yaml
```

4. После установки OpenCost будет доступен по адресу http://opencost.apatsev.org.ru. Перед использованием подождите около 10 минут — за это время OpenCost соберёт необходимые метрики из системы.


## Скрейпинг метрик OpenCost

OpenCost не только читает метрики из VictoriaMetrics, но и **отдаёт свои** (`node_cpu_hourly_cost`, `container_cpu_allocation` и др.) через **активацию ServiceMonitor** — на порту 9003 (`/metrics`). Эти метрики должны **скрейпиться vmagent'ом** и попадать в VictoriaMetrics; иначе в TSDB нет cost-метрик и в UI отображается «No results».

## Подключение MCP OpenCost

В OpenCost встроен MCP-сервер (Model Context Protocol). Он предоставляет инструменты для запроса данных о стоимости кластера: AI-ассистенты (например, Cursor) могут через MCP получать cost-метрики и отвечать на вопросы о расходах.

### Возможности MCP

Через MCP доступны четыре инструмента:

| Инструмент | Назначение |
|------------|------------|
| **get_allocation_costs** | Стоимость по аллокациям (namespace, deployment, pod, container и др.). Агрегация, фильтры, учёт idle/LB, накопление по времени. |
| **get_asset_costs** | Стоимость по активам (ноды, диски и т.п.) за заданное окно времени. |
| **get_cloud_costs** | Облачные расходы: по провайдеру, региону, сервису, аккаунту, категории. Агрегация и фильтрация. |
| **get_efficiency** | Эффективность ресурсов: CPU/память (usage/request), рекомендации по rightsizing и оценка потенциальной экономии. |

Общие параметры: `window` (временное окно), `aggregate` (по чему группировать), `filter` (фильтр по меткам). Для аллокаций можно включать idle, share load balancer, настраивать шаг и разрешение.

MCP доступен по отдельному поддомену. Добавьте сервер в настройки MCP:

```json
{
  "mcpServers": {
    "opencost": {
      "type": "http",
      "url": "http://mcp-opencost.apatsev.org.ru"
    }
  }
}
```

Документация: [OpenCost MCP](https://opencost.io/docs/integrations/mcp/).

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

### Получение метрик через kubectl

Метрики отдаются на порту **9003**, путь `/metrics`. Варианты:

**1. Port-forward и curl (удобно для просмотра локально):**
```bash
# В одном терминале — поднять туннель
kubectl port-forward -n opencost svc/opencost 9003:9003

# В другом — только названия метрик (без значений и комментариев)
curl -s http://localhost:9003/metrics | grep -v '^#' | awk '{print $1}' | sed 's/{.*//' | grep . | sort -u > opencost_metrics.txt
```

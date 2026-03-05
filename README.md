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

На основе этих метрик OpenCost строит cost-модель и экспортирует свои метрики (например, `node_cpu_hourly_cost`, `container_cpu_allocation`). Запросы за прошлые периоды (день, месяц) выполняются через PromQL по уже сохранённым данным в TSDB. Без Prometheus-совместимого хранилища OpenCost не из чего считать стоимость. В этом репозитории в качестве TSDB используется VictoriaMetrics (совместима с Prometheus API).

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

4. После установки OpenCost будет доступен:
  - по адресу http://opencost.apatsev.org.ru;
  - через Ingress-контроллер NGINX (HTTP).
  - Перед использованием подождите около 10 минут — за это время OpenCost соберёт необходимые метрики из системы.


## Скрейпинг метрик OpenCost

OpenCost не только читает метрики из VictoriaMetrics, но и **отдаёт свои** (`node_cpu_hourly_cost`, `container_cpu_allocation` и др.) через **активацию ServiceMonitor** — на порту 9003 (`/metrics`). Эти метрики должны **скрейпиться vmagent'ом** и попадать в VictoriaMetrics; иначе в TSDB нет cost-метрик и в UI отображается «No results».

## Подключение MCP OpenCost

В OpenCost встроен MCP-сервер (Model Context Protocol). Он предоставляет инструменты для запроса данных о стоимости кластера: AI-ассистенты (например, Cursor) могут через MCP получать cost-метрики и отвечать на вопросы о расходах.

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
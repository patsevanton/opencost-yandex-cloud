# opencost-yandex-cloud
Тестирование opencost в yandex cloud


## Зачем OpenCost нужен Prometheus-совместимый TSDB

OpenCost сам не собирает и не хранит метрики. Для расчёта стоимости ему нужна внешняя база временных рядов с Prometheus API, откуда он читает:

- **node-exporter** — использование CPU, памяти, диска на нодах;
- **kube-state-metrics** — запросы/лимиты подов, PVC, состояние нод.

На основе этих метрик OpenCost строит cost-модель и свои метрики (например `node_cpu_hourly_cost`, `container_cpu_allocation`). Запросы за прошлые периоды (день, месяц) выполняются через PromQL по уже сохранённым данным в TSDB. Без Prometheus-совместимого хранилища OpenCost не из чего считать стоимость. В этом репозитории в качестве TSDB используется VictoriaMetrics (совместим с Prometheus API).

## Установка VictoriaMetrics Stack

Для установки VictoriaMetrics Stack в кластер Kubernetes выполните следующие шаги:

1. Добавьте репозиторий Helm-чартов VictoriaMetrics:
```bash
helm repo add vm https://victoriametrics.github.io/helm-charts/
helm repo update
```

2. Получите дефолтные values-файлы:
```bash
helm show values vm/victoria-metrics-k8s-stack > default-vmks-values.yaml
```

3. Установите VictoriaMetrics Stack с включенным Ingress:
```bash
helm upgrade --install --wait \
      vmks vm/victoria-metrics-k8s-stack \
      --namespace vmks --create-namespace \
      --version 0.72.2 \
      --values vmks-values.yaml
```

## Установка OpenCost

Для установки OpenCost в кластер Kubernetes выполните следующие шаги:

1. Добавьте репозиторий OpenCost Helm:
```bash
helm repo add opencost https://opencost.github.io/opencost-helm-chart
helm repo update
```

2. Установите OpenCost используя подготовленный файл значений:
```bash
helm upgrade --install --wait \
   opencost opencost/opencost \
   --namespace opencost \
   --create-namespace \
   --version 2.5.9 \
   --values opencost-values.yaml
```

3. После установки OpenCost будет доступен:
   - По адресу: http://opencost.apatsev.org.ru
   - Через Ingress контроллер NGINX (HTTP)

## Почему OpenCost показывает "No results"

Проверка в кластере (имена сервисов и доступ к VM — в порядке). **Главная причина**: OpenCost не только читает метрики из VictoriaMetrics, но и **отдаёт свои** (`node_cpu_hourly_cost`, `container_cpu_allocation` и др.) на порту 9003 (`/metrics`). Эти метрики должны **скрейпиться vmagent’ом** и попадать в VM; иначе в TSDB нет cost-метрик и UI показывает "No results".

1. **Добавить OpenCost в scrape vmagent** (обязательно). В репозитории есть отдельный манифест `opencost-vmscrapeconfig.yaml` — примените его после установки VMKS и OpenCost:
```bash
kubectl apply -f opencost-vmscrapeconfig.yaml
```

## Подключение MCP OpenCost

В OpenCost встроен MCP-сервер (Model Context Protocol). Он предоставляет инструменты для запроса данных о стоимости кластера — AI-ассистенты (например, Cursor) могут через MCP получать cost-метрики и отвечать на вопросы о расходах.

MCP доступен по отдельному поддомену. Добавьте сервер в настройки MCP (например, в Cursor):

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

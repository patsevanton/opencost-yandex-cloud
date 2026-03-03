# opencost-yandex-cloud

Тестирование OpenCost в Yandex Cloud.

## Зачем OpenCost нужен Prometheus-совместимый TSDB

OpenCost сам не собирает и не хранит метрики. Для расчёта стоимости ему нужна внешняя база временных рядов с Prometheus API, из которой он читает:

- **node-exporter** — использование CPU, памяти, диска на нодах;
- **kube-state-metrics** — запросы/лимиты подов, PVC, состояние нод.

На основе этих метрик OpenCost строит cost-модель и экспортирует свои метрики (например, `node_cpu_hourly_cost`, `container_cpu_allocation`). Запросы за прошлые периоды (день, месяц) выполняются через PromQL по уже сохранённым данным в TSDB. Без Prometheus-совместимого хранилища OpenCost не из чего считать стоимость. В этом репозитории в качестве TSDB используется VictoriaMetrics (совместима с Prometheus API).

## Установка VictoriaMetrics Stack

Для установки VictoriaMetrics Stack в кластер Kubernetes выполните следующие шаги:

1. Добавьте репозиторий Helm-чартов VictoriaMetrics:
```bash
helm repo add vm https://victoriametrics.github.io/helm-charts/
helm repo update
```

2. Сохраните values по умолчанию (опционально, для справки):
```bash
helm show values vm/victoria-metrics-k8s-stack > default-vmks-values.yaml
```

3. Установите VictoriaMetrics Stack с включённым Ingress:
```bash
helm upgrade --install --wait \
      vmks vm/victoria-metrics-k8s-stack \
      --namespace vmks --create-namespace \
      --version 0.72.2 \
      --values vmks-values.yaml
```

### Ресурсы VictoriaMetrics Stack

Чарт по умолчанию выставляет адекватные requests/limits для кластера из 3 нод. Текущее потребление обычно далеко от лимитов:

| Компонент   | Limits (по умолчанию) | Типичное потребление |
|------------|------------------------|------------------------|
| vmselect   | 500m CPU, 1Gi RAM      | ~50m CPU, ~50Mi RAM   |
| vmstorage  | 1 CPU, 1.5Gi RAM       | ~40m CPU, ~200–250Mi  |
| vminsert   | 500m CPU, 500Mi RAM    | ~10m CPU, ~60Mi       |
| vmagent    | 200m CPU, 500Mi RAM    | ~20m CPU, ~50Mi       |

Если запросы OpenCost к VictoriaMetrics тормозят или таймаутят, можно в `vmks-values.yaml` увеличить лимиты для **vmselect** (он обрабатывает PromQL-запросы). OOM и нехватки ресурсов при текущей конфигурации не наблюдается.

## Установка OpenCost

Для установки OpenCost в кластер Kubernetes выполните следующие шаги:

1. Добавьте репозиторий OpenCost Helm:
```bash
helm repo add opencost https://opencost.github.io/opencost-helm-chart
helm repo update
```

2. Установите OpenCost, используя подготовленный файл значений:
```bash
helm upgrade --install --wait \
   opencost opencost/opencost \
   --namespace opencost \
   --create-namespace \
   --version 2.5.9 \
   --values opencost-values.yaml
```

3. После установки OpenCost будет доступен:
   - по адресу http://opencost.apatsev.org.ru;
   - через Ingress-контроллер NGINX (HTTP).

## Устранение неполадок

**Страница долго крутится или запрос обрывается (499)**  
Запросы allocation к VictoriaMetrics (особенно окно 7 дней) могут выполняться 1–2 минуты. Ingress и UI-прокси настроены на таймаут 300 с. Если браузер обрывает запрос раньше:
- откройте с окном «Сегодня» для быстрой загрузки: http://opencost.apatsev.org.ru/?window=today ;
- убедитесь, что применён скрейп метрик OpenCost (`kubectl apply -f opencost-vmscrapeconfig.yaml`), иначе данных для расчёта нет.

**Проверка логов и здоровья**  
```bash
kubectl -n opencost logs -l app.kubernetes.io/name=opencost -c opencost --tail=50
kubectl -n opencost get pods
```

## Скрейпинг метрик OpenCost (vmagent)

OpenCost не только читает метрики из VictoriaMetrics, но и **отдаёт свои** (`node_cpu_hourly_cost`, `container_cpu_allocation` и др.) на порту 9003 (`/metrics`). Эти метрики должны **скрейпиться vmagent’ом** и попадать в VictoriaMetrics; иначе в TSDB нет cost-метрик и в UI отображается «No results». Если проверка в кластере в порядке (имена сервисов и доступ к VictoriaMetrics), чаще всего причина именно в отсутствии этого скрейпа.

Для этого примените `opencost-vmscrapeconfig.yaml` после установки VMKS и OpenCost:
```bash
kubectl apply -f opencost-vmscrapeconfig.yaml
```

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

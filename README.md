# opencost-yandex-cloud
Тестирование opencost в yandex cloud

VictoriaMetrics обязателен.

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

# opencost-yandex-cloud
Тестирование opencost в yandex cloud

## Установка VictoriaMetrics Stack

Для установки VictoriaMetrics Stack в кластер Kubernetes выполните следующие шаги:

1. Добавьте репозиторий Helm-чартов VictoriaMetrics:
   ```console
   helm repo add vm https://victoriametrics.github.io/helm-charts/
   helm repo update
   ```

2. Установите VictoriaMetrics Stack с включенным Ingress:
   ```console
    helm upgrade --install --wait \
        vmks vm/victoria-metrics-k8s-stack \
        --namespace vmks --create-namespace \
        --version 0.63.5 \
        --values vmks-values.yaml
   ```

## Установка OpenCost

Для установки OpenCost в кластер Kubernetes выполните следующие шаги:

1. Добавьте репозиторий OpenCost Helm:
   ```console
   helm repo add opencost https://opencost.github.io/opencost-helm-chart
   helm repo update
   ```

2. Получите дефолтные values-файлы:
   ```console
   helm show values opencost/opencost > default-opencost-values.yaml
   ```

4. Установите OpenCost с включенным Ingress для домена opencost.apatsev.org.ru:
   ```console
   helm install opencost opencost/opencost \
     --namespace opencost \
     --create-namespace \
     --set opencost.ui.ingress.enabled=true \
     --set opencost.ui.ingress.hosts[0].host=opencost.apatsev.org.ru \
     --set opencost.ui.ingress.hosts[0].paths[0].path=/ \
     --set opencost.ui.ingress.ingressClassName=nginx
   ```

После установки OpenCost будет доступен по адресу: http://opencost.apatsev.org.ru

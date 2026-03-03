## Установка VictoriaMetrics Stack

Для установки VictoriaMetrics Stack в кластер Kubernetes выполните следующие шаги:

1. Добавьте репозиторий Helm-чартов VictoriaMetrics:
   ```console
   helm repo add vm https://victoriametrics.github.io/helm-charts/
   helm repo update
   ```

2. Получите дефолтные values-файлы:
   ```console
   helm show values vm/victoria-metrics-k8s-stack > default-vmks-values.yaml
   ```

3. Установите VictoriaMetrics Stack с включенным Ingress:
   ```console
   helm upgrade --install --wait \
       vmks vm/victoria-metrics-k8s-stack \
       --namespace vmks --create-namespace \
       --version 0.72.2 \
       --values vmks-values.yaml
   ```

# opencost-yandex-cloud
Тестирование opencost в yandex cloud

## Установка OpenCost

Для установки OpenCost в кластер Kubernetes выполните следующие шаги:

1. Добавьте репозиторий OpenCost Helm:
   ```console
   helm repo add opencost https://opencost.github.io/opencost-helm-chart
   helm repo update
   ```

2. Установите OpenCost используя подготовленный файл значений:
   ```console
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

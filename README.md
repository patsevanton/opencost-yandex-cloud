# opencost-yandex-cloud
Тестирование opencost в yandex cloud

## Установка OpenCost

Для установки OpenCost в кластер Kubernetes выполните следующие шаги:

1. Добавьте репозиторий OpenCost Helm:
   ```console
   helm repo add opencost https://opencost.github.io/opencost-helm-chart
   helm repo update
   ```

2. Установите OpenCost с включенным Ingress для домена opencost.apatsev.org.ru:
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


## Установка Prometheus Stack (kube-prometheus-stack)

Для установки Prometheus Stack в кластер Kubernetes выполните следующие шаги:

1. Добавьте репозиторий Helm-чартов Prometheus Community:
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
```

2. Установите kube-prometheus-stack:
```bash
helm upgrade --install --wait --timeout 10m \
      prometheus prometheus-community/kube-prometheus-stack \
      --namespace monitoring --create-namespace \
      --version 67.2.0
```

## Установка OpenCost

Для установки OpenCost в кластер Kubernetes выполните следующие шаги:

1. Добавьте репозиторий OpenCost Helm:
```bash
helm repo add opencost https://opencost.github.io/opencost-helm-chart
helm repo update
```

2. Создайте namespace и примените ConfigMap
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

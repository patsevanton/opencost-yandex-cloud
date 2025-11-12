resource "yandex_iam_service_account" "sa-k8s-editor" {
  folder_id = coalesce(local.folder_id, data.yandex_client_config.client.folder_id)
  name      = "sa-k8s-editor"
}

resource "yandex_resourcemanager_folder_iam_member" "sa-k8s-editor-permissions" {
  folder_id = coalesce(local.folder_id, data.yandex_client_config.client.folder_id)
  role      = "editor"

  member = "serviceAccount:${yandex_iam_service_account.sa-k8s-editor.id}"
}

resource "time_sleep" "wait_sa" {
  create_duration = "20s"
  depends_on      = [
    yandex_iam_service_account.sa-k8s-editor,
    yandex_resourcemanager_folder_iam_member.sa-k8s-editor-permissions
  ]
}

resource "yandex_kubernetes_cluster" "opencost" {
  name       = "opencost"
  folder_id  = coalesce(local.folder_id, data.yandex_client_config.client.folder_id)
  network_id = yandex_vpc_network.opencost.id

  master {
    version = "1.30"
    zonal {
      zone      = yandex_vpc_subnet.opencost-a.zone
      subnet_id = yandex_vpc_subnet.opencost-a.id
    }

    public_ip = true
  }

  service_account_id      = yandex_iam_service_account.sa-k8s-editor.id
  node_service_account_id = yandex_iam_service_account.sa-k8s-editor.id

  release_channel = "STABLE"

  depends_on = [time_sleep.wait_sa]
}

resource "yandex_kubernetes_node_group" "k8s-node-group" {
  description = "Node group for the Managed Service for Kubernetes cluster"
  name        = "k8s-node-group"
  cluster_id  = yandex_kubernetes_cluster.opencost.id
  version     = "1.30"

  scale_policy {
    fixed_scale {
      size = 3
    }
  }

  allocation_policy {
    location { zone = yandex_vpc_subnet.opencost-a.zone }
    location { zone = yandex_vpc_subnet.opencost-b.zone }
    location { zone = yandex_vpc_subnet.opencost-d.zone }
  }

  instance_template {
    platform_id = "standard-v2"

    network_interface {
      nat = true
      subnet_ids = [
        yandex_vpc_subnet.opencost-a.id,
        yandex_vpc_subnet.opencost-b.id,
        yandex_vpc_subnet.opencost-d.id
      ]
    }

    resources {
      memory = 20
      cores  = 4
    }

    boot_disk {
      type = "network-ssd"
      size = 128
    }
  }
}

provider "helm" {
  kubernetes {
    host                   = yandex_kubernetes_cluster.opencost.master[0].external_v4_endpoint
    cluster_ca_certificate = yandex_kubernetes_cluster.opencost.master[0].cluster_ca_certificate

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      args        = ["k8s", "create-token"]
      command     = "yc"
    }
  }
}

resource "helm_release" "ingress_nginx" {
  name             = "ingress-nginx"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  version          = "4.11.8"
  namespace        = "ingress-nginx"
  create_namespace = true
  depends_on       = [yandex_kubernetes_cluster.opencost]

  set {
    name  = "controller.service.loadBalancerIP"
    value = yandex_vpc_address.addr.external_ipv4_address[0].address
  }
}

output "k8s_cluster_credentials_command" {
  value = "yc managed-kubernetes cluster get-credentials --id ${yandex_kubernetes_cluster.opencost.id} --external --force"
}

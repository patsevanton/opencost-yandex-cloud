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
    version = "1.32"
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
  version     = "1.32"

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
  kubernetes = {
    host                   = yandex_kubernetes_cluster.opencost.master[0].external_v4_endpoint
    cluster_ca_certificate = yandex_kubernetes_cluster.opencost.master[0].cluster_ca_certificate

    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"
      args        = ["k8s", "create-token"]
      command     = "yc"
    }
  }
}

resource "helm_release" "ingress_nginx" {
  name             = "ingress-nginx"
  chart            = "oci://cr.yandex/yc-marketplace/yandex-cloud/ingress-nginx/chart/ingress-nginx"
  version          = "4.13.0"
  namespace        = "ingress-nginx"
  create_namespace = true

  depends_on = [
    yandex_kubernetes_cluster.opencost
  ]

  values = [
    yamlencode({
      controller = {
        podLabels = {
          team = "ingress"
        }
        service = {
          loadBalancerIP = yandex_vpc_address.addr.external_ipv4_address[0].address
        }
        config = {
          log-format-escape-json = "true"
          log-format-upstream = trimspace(<<-EOT
            {"ts":"$time_iso8601","http":{"request_id":"$req_id","method":"$request_method","status_code":$status,"url":"$host$request_uri","host":"$host","uri":"$request_uri","request_time":$request_time,"user_agent":"$http_user_agent","protocol":"$server_protocol","trace_session_id":"$http_trace_session_id","server_protocol":"$server_protocol","content_type":"$sent_http_content_type","bytes_sent":"$bytes_sent"},"nginx":{"x-forward-for":"$proxy_add_x_forwarded_for","remote_addr":"$proxy_protocol_addr","http_referrer":"$http_referer"}}
          EOT
          )
        }
      }
    })
  ]
}

output "k8s_cluster_credentials_command" {
  value = "yc managed-kubernetes cluster get-credentials --id ${yandex_kubernetes_cluster.opencost.id} --external --force"
}

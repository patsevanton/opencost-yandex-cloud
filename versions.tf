terraform {
  required_providers {
    yandex = {
      source  = "yandex-cloud/yandex"
      version = ">= 0.72.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = ">= 3.0.0"
    }
  }
  required_version = ">= 1.3"
}

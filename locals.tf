data "yandex_client_config" "client" {}

resource "random_password" "kafka" {
  length      = 20
  special     = false
  min_numeric = 4
  min_upper   = 4
}

resource "random_password" "clickhouse" {
  length      = 20
  special     = false
  min_numeric = 4
  min_upper   = 4
}

resource "random_password" "redis" {
  length      = 20
  special     = false
  min_numeric = 4
  min_upper   = 4
}

resource "random_password" "postgres" {
  length      = 20
  special     = false
  min_numeric = 4
  min_upper   = 4
}

resource "random_password" "opencost_admin_password" {
  length      = 20
  special     = false
  min_numeric = 4
  min_upper   = 4
}

locals {
  folder_id            = data.yandex_client_config.client.folder_id
  opencost_admin_password = random_password.opencost_admin_password.result
  kafka_user           = "opencost"
  kafka_password       = random_password.kafka.result
  clickhouse_user      = "opencost"
  clickhouse_password  = random_password.clickhouse.result
  redis_password       = random_password.redis.result
  postgres_password    = random_password.postgres.result
  filestore_bucket     = "opencost-bucket-apatsev-filestore-test"
  nodestore_bucket     = "opencost-bucket-apatsev-nodestore-test"
}

output "generated_passwords" {
  description = "Map of generated passwords for services"
  value = {
    kafka_password      = random_password.kafka.result
    clickhouse_password = random_password.clickhouse.result
    redis_password      = random_password.redis.result
    postgres_password   = random_password.postgres.result
  }
  sensitive = true
}

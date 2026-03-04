data "yandex_client_config" "client" {}

locals {
  folder_id = data.yandex_client_config.client.folder_id
}

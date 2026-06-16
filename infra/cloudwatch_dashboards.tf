locals {
  cloudwatch_dashboard_files = fileset("${path.module}/../gateway/dashboards", "*.json")
}

resource "aws_cloudwatch_dashboard" "observability" {
  for_each = local.cloudwatch_dashboard_files

  dashboard_name = "LLMGateway-${var.namespace}-${replace(trimsuffix(each.value, ".json"), "_", "-")}"
  dashboard_body = replace(
    file("${path.module}/../gateway/dashboards/${each.value}"),
    "/ecs/gw/gateway",
    aws_cloudwatch_log_group.gw.name
  )
}

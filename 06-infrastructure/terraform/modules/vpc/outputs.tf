output "vpc_id" {
  description = "The ID of the VPC created by this module."
  value       = aws_vpc.this.id
}

output "vpc_cidr" {
  description = "The primary IPv4 CIDR block of the VPC (always 10.0.0.0/16)."
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "List of subnet IDs for the public subnets (10.0.1.0/24, 10.0.2.0/24). These subnets host the ALB and NAT Gateways. Resources placed here receive public IPs."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "List of subnet IDs for the private subnets (10.0.11.0/24, 10.0.12.0/24). These subnets host ECS Fargate tasks. Outbound internet traffic routes through the NAT Gateway in the same AZ."
  value       = aws_subnet.private[*].id
}

output "isolated_subnet_ids" {
  description = "List of subnet IDs for the isolated subnets (10.0.21.0/24, 10.0.22.0/24). These subnets host VPC Interface Endpoints and the MongoDB Atlas PrivateLink ENI. No route to the internet exists."
  value       = aws_subnet.isolated[*].id
}

output "nat_gateway_ids" {
  description = "List of NAT Gateway IDs (one per AZ). Useful for downstream modules that need to reference NAT GW associations or monitor NAT GW CloudWatch metrics."
  value       = aws_nat_gateway.this[*].id
}

output "public_route_table_id" {
  description = "ID of the single public route table (shared across both public subnets). Callers can add additional routes (e.g., S3 Gateway Endpoint) to this table."
  value       = aws_route_table.public.id
}

output "private_route_table_ids" {
  description = "List of private route table IDs (one per AZ). Callers can add additional routes (e.g., S3 Gateway Endpoint) to these tables. Index 0 = AZ[0], index 1 = AZ[1]."
  value       = aws_route_table.private[*].id
}

output "isolated_route_table_id" {
  description = "ID of the single isolated route table (shared across both isolated subnets). No default route exists on this table. Callers can add VPC Endpoint associations."
  value       = aws_route_table.isolated.id
}

output "flow_log_group_name" {
  description = "Name of the CloudWatch Log Group that receives VPC Flow Logs. Useful for constructing CloudWatch Insights queries or metric filters in upstream modules."
  value       = aws_cloudwatch_log_group.flow_logs.name
}

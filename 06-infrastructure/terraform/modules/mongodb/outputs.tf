# -----------------------------------------------------------------------------
# MongoDB Atlas Module — Outputs
# -----------------------------------------------------------------------------

output "cluster_id" {
  description = "Unique ID of the MongoDB Atlas cluster."
  value       = mongodbatlas_cluster.this.cluster_id
}

output "cluster_connection_strings" {
  description = "Map of connection strings for the Atlas cluster. Includes standard SRV URI and the private (PrivateLink) SRV URI."
  value = {
    standard         = mongodbatlas_cluster.this.connection_strings[0].standard_srv
    private_srv      = mongodbatlas_cluster.this.connection_strings[0].private_srv
    private_endpoint = try(mongodbatlas_cluster.this.connection_strings[0].private_endpoint[0].srv_connection_string, null)
  }
  sensitive = true
}

output "private_link_endpoint_id" {
  description = "Atlas private link ID used to track the PrivateLink endpoint pair."
  value       = mongodbatlas_privatelink_endpoint.this.private_link_id
}

output "aws_vpc_endpoint_id" {
  description = "AWS VPC Interface Endpoint ID created for the Atlas PrivateLink connection."
  value       = aws_vpc_endpoint.mongodb_atlas.id
}

output "database_user" {
  description = "Username of the application database user created in Atlas."
  value       = mongodbatlas_database_user.app.username
}

output "project_id" {
  description = "MongoDB Atlas project ID. Required by other Atlas resources or modules."
  value       = mongodbatlas_project.this.id
}

output "cluster_name" {
  description = "Name of the provisioned Atlas cluster."
  value       = mongodbatlas_cluster.this.name
}

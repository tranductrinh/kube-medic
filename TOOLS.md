# KubeMedic Tools Reference

This document describes all tools available to KubeMedic agents.

## Kubernetes Agent Tools (Read-Only)

> **Note:** The Kubernetes agent requires sufficient RBAC permissions to perform these operations. Ensure the service
> account has read access to namespaces, pods, deployments, services, configmaps, secrets, events, nodes, and ingresses.

| Tool               | Description                                       |
|--------------------|---------------------------------------------------|
| `get_events`       | Get Kubernetes events (scheduling, crashes, etc.) |
| `get_node_details` | Get node capacity, conditions, and taints         |
| `get_pod_details`  | Get detailed information about a specific pod     |
| `get_pod_logs`     | Retrieve logs from a pod/container                |
| `list_configmaps`  | List ConfigMaps (keys only, not values)           |
| `list_deployments` | List deployments with replica status              |
| `list_ingresses`   | List ingresses with routing rules and backends    |
| `list_namespaces`  | List all namespaces in the cluster                |
| `list_nodes`       | List cluster nodes with status                    |
| `list_pods`        | List pods with status and restart counts          |
| `list_secrets`     | List Secret names (not values)                    |
| `list_services`    | List services with types and endpoints            |

## Prometheus Agent Tools

| Tool                     | Description                                     |
|--------------------------|-------------------------------------------------|
| `prometheus_query`       | Execute PromQL instant queries                  |
| `prometheus_query_range` | Execute PromQL range queries for trend analysis |

## Network Agent Tools

| Tool         | Description                                                                     |
|--------------|---------------------------------------------------------------------------------|
| `http_check` | Check HTTP/HTTPS endpoint accessibility (status code, response time, redirects) |

## Email Agent Tools

| Tool         | Description                                         |
|--------------|-----------------------------------------------------|
| `send_email` | Send email notifications with investigation results |

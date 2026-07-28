# Deployment Platform Abstraction

RAGuard AI is fundamentally infrastructure-agnostic. 
The core container (`raguard:1.0.0`) can run on any orchestrator.

## Reference Architectures Supported:
1. **Docker Compose (Local/Single-Node)**: Best for isolated PoCs or single-tenant servers.
2. **Docker Swarm**: Built-in multi-node orchestration.
3. **Kubernetes (K8s)**: Enterprise standard. Requires a custom Helm chart or kustomize overlay mapping our environment variables and volume mounts.
4. **AWS ECS / Fargate**: Deploy using the Docker container directly, managing state in RDS/ElastiCache.
5. **GCP Cloud Run**: Fully managed serverless platform; attach Cloud SQL for PostgreSQL.
6. **Azure Container Apps**: Map environment variables to Key Vault secrets.

The repository provides the `docker-compose.prod.yml` as the universal lowest common denominator.

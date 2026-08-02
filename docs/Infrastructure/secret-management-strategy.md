# Secret Management Strategy

## Policy
RAGuard AI adheres to the principle of Zero Trust for secrets.
No secrets, credentials, or API keys shall be stored in version control.

## Supported Providers
We recommend injecting the `.env.prod` file at runtime via one of the following:
- **AWS Secrets Manager** / Parameter Store
- **HashiCorp Vault**
- **GCP Secret Manager**
- **Azure Key Vault**
- **Kubernetes Secrets**

## Secret Injection (Docker/Swarm)
Use external secrets bound via Docker Swarm or injected directly into the
container environment by the CI/CD pipeline prior to startup.

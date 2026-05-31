# Production Deployment Guide

## Architecture

```
GitHub Actions
  → Azure Container Registry (image store)
    → Azure Container Apps (API runtime)
      ↑ reads secrets from
    Azure Key Vault
  → Azure Static Web Apps (SPA)
      ↑ calls
    Azure Container Apps (API)
      ↑ reads from
    Azure Database for PostgreSQL
```

## Prerequisites

- Azure subscription with Contributor access
- Azure CLI: `az login`
- Docker

## Step 1 — Azure resources

```bash
# Variables
RG=rg-cost-estimator-prod
LOCATION=eastus
ACR=sowcalcacr                        # must be globally unique
ACA_ENV=cost-estimator-env
ACA_APP=cost-estimator-api
KV=kv-cost-estimator                  # must be globally unique
PG_SERVER=cost-estimator-pg

# Resource group
az group create --name $RG --location $LOCATION

# Container Registry
az acr create --name $ACR --resource-group $RG --sku Basic --admin-enabled true

# Key Vault
az keyvault create --name $KV --resource-group $RG --location $LOCATION

# PostgreSQL Flexible Server
az postgres flexible-server create \
  --name $PG_SERVER \
  --resource-group $RG \
  --location $LOCATION \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --database-name sow_calc \
  --admin-user sow_calc \
  --admin-password "$(openssl rand -base64 24)" \
  --public-access None    # private endpoint only

# Container Apps environment
az containerapp env create \
  --name $ACA_ENV \
  --resource-group $RG \
  --location $LOCATION
```

## Step 2 — Secrets in Key Vault

```bash
# Generate strong secrets
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
PG_PASS=$(az postgres flexible-server show-connection-string \
  --server-name $PG_SERVER --database-name sow_calc \
  --admin-user sow_calc --query connectionStrings.python -o tsv)

az keyvault secret set --vault-name $KV --name "SecretKey"    --value "$SECRET_KEY"
az keyvault secret set --vault-name $KV --name "DatabaseUrl"  --value "$PG_PASS"
az keyvault secret set --vault-name $KV --name "AuthentikIssuer" \
  --value "https://your-authentik-domain/application/o/cost-estimator-api/"

# The Container App managed identity reads secrets at runtime.
# Set the Key Vault references in the Container App environment variables:
#   secretref:SecretKey → SECRET_KEY
#   secretref:DatabaseUrl → DATABASE_URL
```

## Step 3 — GitHub Secrets

Add these in **GitHub → Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `AZURE_CREDENTIALS` | Output of `az ad sp create-for-rbac --sdk-auth` |
| `AZURE_CONTAINER_REGISTRY` | `sowcalcacr.azurecr.io` |
| `AZURE_REGISTRY_USERNAME` | ACR admin username |
| `AZURE_REGISTRY_PASSWORD` | ACR admin password |
| `AZURE_RESOURCE_GROUP` | `rg-cost-estimator-prod` |
| `AZURE_CONTAINER_APP_NAME` | `cost-estimator-api` |

Generate the service principal:
```bash
az ad sp create-for-rbac \
  --name "sp-cost-estimator-deploy" \
  --role contributor \
  --scopes /subscriptions/<sub-id>/resourceGroups/$RG \
  --sdk-auth
```

## Step 4 — Container App configuration

```bash
az containerapp create \
  --name $ACA_APP \
  --resource-group $RG \
  --environment $ACA_ENV \
  --image "$ACR.azurecr.io/cost-estimator-api:latest" \
  --registry-server "$ACR.azurecr.io" \
  --registry-username $(az acr credential show --name $ACR --query username -o tsv) \
  --registry-password $(az acr credential show --name $ACR --query passwords[0].value -o tsv) \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 5 \
  --cpu 0.5 \
  --memory 1Gi \
  --env-vars \
    ENVIRONMENT=production \
    AUTH_MODE=oidc \
    ALLOWED_ORIGINS="https://your-spa-domain.azurestaticapps.net" \
    SECRET_KEY=secretref:SecretKey \
    DATABASE_URL=secretref:DatabaseUrl \
    AUTHENTIK_ISSUER=secretref:AuthentikIssuer
```

## Step 5 — Postgres TLS

The DATABASE_URL for production must include SSL:
```
postgresql+psycopg2://sow_calc:<pass>@<server>.postgres.database.azure.com/sow_calc?sslmode=require
```

Azure PostgreSQL Flexible Server enforces TLS 1.2+ by default. No additional
config needed — just include `?sslmode=require` in the connection string.

## Step 6 — CORS

Set `ALLOWED_ORIGINS` to your SPA's production URL(s):
```
ALLOWED_ORIGINS=https://cost-estimator.azurestaticapps.net,https://cost.yourcompany.com
```

The API rejects cross-origin requests from any other origin in production.

## Step 7 — Trigger the first deploy

```bash
git push origin master
```

GitHub Actions will:
1. Run tests against a Postgres service container
2. Build and push the Docker image to ACR (with layer caching)
3. Deploy the new image to Container Apps (requires `production` environment approval)

## Monitoring

```bash
# Stream live logs
az containerapp logs show --name $ACA_APP --resource-group $RG --follow

# Check revision status
az containerapp revision list --name $ACA_APP --resource-group $RG --output table
```

## Rollback

```bash
# List revisions
az containerapp revision list --name $ACA_APP --resource-group $RG --output table

# Activate a previous revision
az containerapp revision activate \
  --revision <revision-name> \
  --name $ACA_APP \
  --resource-group $RG
```

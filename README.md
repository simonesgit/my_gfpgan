# GFPGAN Face Restoration API

A FastAPI-based REST API for face restoration using GFPGAN, deployed on Azure Container Apps.

## Features

- Asynchronous image processing
- RESTful API endpoints
- Containerized deployment
- Stateless architecture

## API Endpoints

### Submit Image for Processing
```bash
POST /submit

```
- Accepts image file upload
- Returns job ID and status URL
- Processes image asynchronously

### Check Processing Status
```bash
GET /status/{job_id}
```
- Returns processing status
- Downloads restored image when complete

## Deployment Guide

### Prerequisites

1. Azure CLI installed
2. Azure subscription
3. Docker installed locally
4. Git repository with the code

### Step 1: Azure Resources Setup

```bash
# Login to Azure
az login

# Create Resource Group
az group create --name gfpgan-rg --location eastus

# Create Container Registry
az acr create --resource-group gfpgan-rg \
    --name gfpganregistry --sku Basic

# Enable admin access
az acr update -n gfpganregistry --admin-enabled true
```

### Step 2: Build and Push Container Image

```bash
# Build the image
az acr build --registry gfpganregistry \
    --image gfpgan:v1 .
```

### Step 3: Create Container App

```bash
# Create Container App Environment
az containerapp env create \
    --name gfpgan-env \
    --resource-group gfpgan-rg \
    --location eastus

# Create Container App
az containerapp create \
    --name gfpgan-app \
    --resource-group gfpgan-rg \
    --environment gfpgan-env \
    --image gfpganregistry.azurecr.io/gfpgan:v1 \
    --registry-server gfpganregistry.azurecr.io \
    --cpu 2 \
    --memory 4Gi \
    --min-replicas 1 \
    --max-replicas 1

# Update ingress settings
az containerapp ingress update \
    --name gfpgan-app \
    --resource-group gfpgan-rg \
    --target-port 8000 \
    --transport http \
    --timeout 300
```

### Step 4: Usage Example

Submit an image for processing:
```bash
curl -X POST \
  -F "file=@/path/to/image.jpg" \
  https://your-app-url/submit
```

Check processing status and get result:
```bash
curl https://your-app-url/status/job_id \
  --output restored_image.jpg
```

## Configuration

The application is configured with:
- 2 CPU cores
- 4GB memory
- 300-second timeout
- HTTP transport
- Single replica

## Maintenance

To update the application:

```bash
# Build new version
az acr build --registry gfpganregistry \
    --image gfpgan:v2 .

# Update container app
az containerapp update \
    --name gfpgan-app \
    --resource-group gfpgan-rg \
    --image gfpganregistry.azurecr.io/gfpgan:v2
```

## Troubleshooting

View application logs:
```bash
az containerapp logs show \
    --name gfpgan-app \
    --resource-group gfpgan-rg \
    --follow
```
```

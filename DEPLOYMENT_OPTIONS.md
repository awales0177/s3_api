# Deployment Options Guide

This guide explains different ways to handle configuration and credentials in your S3 API deployment.

## Option 1: Keep .env in Container (Current Setup)

### ✅ When to Use:
- **Local development**
- **Simple deployments**
- **Non-sensitive configuration**
- **Quick testing**

### How it Works:
- `.env` file is included in the container
- Environment variables are loaded from the file
- Works with both explicit credentials and IRSA

### Usage:
```bash
# Build and run locally
docker build -t s3-api:dev -f Dockerfile.dev .
docker run -p 8000:8000 s3-api:dev
```

### Pros:
- ✅ Simple setup
- ✅ Works for development
- ✅ No Kubernetes configuration needed

### Cons:
- ❌ Credentials in container image
- ❌ Not suitable for production
- ❌ Hard to rotate credentials

---

## Option 2: Remove .env for Production (Recommended)

### ✅ When to Use:
- **Production deployments**
- **Kubernetes with IRSA**
- **Security-sensitive environments**
- **CI/CD pipelines**

### How it Works:
- `.env` file is excluded from container (via `.dockerignore`)
- Configuration comes from Kubernetes ConfigMaps
- Credentials come from IRSA or Kubernetes Secrets

### Usage:

#### 1. Build Production Image:
```bash
# Build without .env file
docker build -t s3-api:prod .
```

#### 2. Deploy to Kubernetes:
```bash
# Apply ConfigMap
kubectl apply -f k8s-configmap.yaml

# Apply deployment
kubectl apply -f k8s-deployment.yaml
```

### Pros:
- ✅ No credentials in container
- ✅ Secure credential management
- ✅ Easy configuration updates
- ✅ Production-ready

### Cons:
- ❌ More complex setup
- ❌ Requires Kubernetes knowledge

---

## Option 3: Hybrid Approach (Best of Both)

### Development:
- Use `Dockerfile.dev` with `.env` file
- Keep credentials in `.env` for local development

### Production:
- Use `Dockerfile` without `.env` file
- Use Kubernetes ConfigMaps and IRSA

### File Structure:
```
s3_api/
├── Dockerfile          # Production (no .env)
├── Dockerfile.dev      # Development (with .env)
├── .dockerignore       # Excludes .env from production builds
├── k8s-configmap.yaml  # Kubernetes configuration
├── k8s-deployment.yaml # Kubernetes deployment
└── .env               # Development only
```

---

## Configuration Management

### Development (.env file):
```bash
S3_MODE=true
S3_BUCKET_NAME=dh-api-test
S3_FOLDER_PREFIX=dh-api
AWS_REGION=us-east-2
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
```

### Production (Kubernetes ConfigMap):
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: s3-api-config
data:
  S3_MODE: "true"
  S3_BUCKET_NAME: "dh-api-test"
  S3_FOLDER_PREFIX: "dh-api"
  AWS_REGION: "us-east-2"
  # No credentials - uses IRSA
```

---

## Build Commands

### Development Build:
```bash
docker build -t s3-api:dev -f Dockerfile.dev .
```

### Production Build:
```bash
docker build -t s3-api:prod .
```

### Verify .env is Excluded:
```bash
# Check what's in the production image
docker run --rm s3-api:prod ls -la | grep .env
# Should return nothing if .env is excluded
```

---

## Deployment Commands

### Local Development:
```bash
# Using Docker
docker run -p 8000:8000 s3-api:dev

# Using Python directly
python main.py
```

### Kubernetes Production:
```bash
# Apply configuration
kubectl apply -f k8s-configmap.yaml

# Apply deployment
kubectl apply -f k8s-deployment.yaml

# Check status
kubectl get pods -l app=s3-api
kubectl logs -l app=s3-api
```

---

## Security Considerations

### ✅ Secure Practices:
- Use IRSA for production
- Exclude `.env` from production builds
- Use Kubernetes Secrets for sensitive data
- Rotate credentials regularly

### ❌ Avoid:
- Hardcoding credentials in code
- Including `.env` in production containers
- Using root user in containers
- Storing credentials in ConfigMaps

---

## Troubleshooting

### Development Issues:
```bash
# Check if .env is loaded
docker run --rm s3-api:dev env | grep S3

# Check application logs
docker run --rm s3-api:dev python -c "from config import Config; print(Config.S3_BUCKET_NAME)"
```

### Production Issues:
```bash
# Check ConfigMap
kubectl get configmap s3-api-config -o yaml

# Check pod environment
kubectl exec -it POD_NAME -- env | grep S3

# Check IRSA
kubectl exec -it POD_NAME -- aws sts get-caller-identity
```

---

## Recommendation

**Use the Hybrid Approach:**

1. **Development**: Keep `.env` file, use `Dockerfile.dev`
2. **Production**: Remove `.env` file, use Kubernetes ConfigMaps + IRSA
3. **CI/CD**: Build production images without `.env`

This gives you the simplicity of `.env` for development while maintaining security for production.

# IRSA (IAM Roles for Service Accounts) Setup Guide

This guide explains how to configure your S3 API to use IRSA for secure, credential-free access to AWS S3.

## What is IRSA?

IRSA (IAM Roles for Service Accounts) allows Kubernetes pods to assume IAM roles without storing AWS credentials in environment variables or files. This is the recommended approach for production Kubernetes deployments.

## Prerequisites

- EKS cluster with IRSA enabled
- AWS CLI configured
- kubectl configured
- Your S3 bucket and folder structure ready

## Step 1: Create IAM Role

1. **Create a trust policy** for your EKS cluster:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/oidc.eks.REGION.amazonaws.com/id/YOUR_OIDC_ID"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.REGION.amazonaws.com/id/YOUR_OIDC_ID:sub": "system:serviceaccount:default:s3-api-service-account",
          "oidc.eks.REGION.amazonaws.com/id/YOUR_OIDC_ID:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
```

2. **Create the IAM role** with the trust policy above

3. **Attach S3 permissions** to the role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:HeadObject"
      ],
      "Resource": [
        "arn:aws:s3:::dh-api-test",
        "arn:aws:s3:::dh-api-test/*"
      ]
    }
  ]
}
```

## Step 2: Configure Your Application

### Environment Variables for IRSA

Your `.env` file should look like this:

```bash
# S3 Configuration
S3_MODE=true
S3_BUCKET_NAME=dh-api-test
S3_FOLDER_PREFIX=dh-api
AWS_REGION=us-east-2

# Leave these empty for IRSA
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=

# Other configuration
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

### Kubernetes Deployment

Use the provided `k8s-deployment.yaml` file, but update:

1. **Replace the IAM role ARN** in the service account annotation
2. **Update the image** to your container registry
3. **Adjust resource limits** as needed

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: s3-api-service-account
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::YOUR_ACCOUNT_ID:role/YOUR_IAM_ROLE_NAME
```

## Step 3: Deploy to Kubernetes

1. **Build and push your container image:**

```bash
# Build the image
docker build -t your-registry/s3-api:latest .

# Push to your registry
docker push your-registry/s3-api:latest
```

2. **Deploy to Kubernetes:**

```bash
# Apply the deployment
kubectl apply -f k8s-deployment.yaml

# Check the deployment
kubectl get pods -l app=s3-api

# Check logs
kubectl logs -l app=s3-api
```

## Step 4: Verify IRSA is Working

1. **Check the pod logs** for IRSA initialization:

```bash
kubectl logs -l app=s3-api | grep "IAM role"
```

You should see:
```
INFO:services.s3_service:S3 client initialized with IAM role (IRSA) or default credentials
```

2. **Test the S3 connection** via the API:

```bash
# Get the service URL
kubectl get service s3-api-service

# Test S3 connection
curl http://SERVICE_IP/api/debug/s3
```

Expected response:
```json
{
  "s3_mode": true,
  "s3_available": true,
  "bucket_name": "dh-api-test",
  "aws_region": "us-east-2",
  "message": "S3 is available"
}
```

## Step 5: Test Data Operations

1. **Test reading data:**

```bash
curl http://SERVICE_IP/api/models
```

2. **Test search functionality:**

```bash
curl "http://SERVICE_IP/api/search?q=test"
```

## Troubleshooting

### Common Issues

1. **"S3 service not available"**
   - Check IAM role trust policy
   - Verify service account annotation
   - Check OIDC provider configuration

2. **"Access Denied" errors**
   - Verify S3 permissions in IAM role
   - Check bucket policy
   - Ensure role is attached to service account

3. **"NoSuchKey" errors**
   - Verify S3_FOLDER_PREFIX is correct
   - Check if files exist in the bucket
   - Verify bucket name

### Debug Commands

```bash
# Check service account
kubectl describe serviceaccount s3-api-service-account

# Check pod environment
kubectl exec -it POD_NAME -- env | grep AWS

# Check IAM role assumption
kubectl exec -it POD_NAME -- aws sts get-caller-identity

# Check S3 access
kubectl exec -it POD_NAME -- aws s3 ls s3://dh-api-test/dh-api/
```

## Security Benefits

- ✅ **No credentials in environment variables**
- ✅ **No credentials in container images**
- ✅ **Automatic credential rotation**
- ✅ **Fine-grained permissions**
- ✅ **Audit trail through CloudTrail**

## Local Development

For local development, you can still use explicit credentials:

```bash
# Local .env file
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

The application will automatically detect and use the appropriate authentication method.

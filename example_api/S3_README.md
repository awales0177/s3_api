# S3 Integration for Data Catalog API

This document explains how to configure and use the Data Catalog API with Amazon S3 instead of local files.

## 🚀 **Overview**

The API now supports three data source modes:
1. **S3 Mode** - Read/write from S3 bucket (recommended for production)
2. **Local Mode** - Read/write from local `_data` directory (for development/testing)
3. **GitHub Mode** - Read from GitHub repository (legacy mode)

## 🔧 **Setup S3 Mode**

### 1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

### 2. **Configure Environment Variables**
Create a `.env` file in the `api` directory:

```bash
# Data Source Mode
S3_MODE=true

# S3 Configuration
S3_BUCKET_NAME=your-data-catalog-bucket
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Optional: Other settings
CACHE_DURATION_MINUTES=15
HOST=0.0.0.0
PORT=8000
```

### 3. **AWS Credentials Setup**

#### Option A: Environment Variables
```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
```

#### Option B: AWS CLI Configuration
```bash
aws configure
```

#### Option C: IAM Role (for EC2/ECS)
If running on AWS infrastructure, use IAM roles instead of access keys.

### 4. **S3 Bucket Structure**
Your S3 bucket should contain the JSON files in this structure:
```
your-bucket/
├── applications.json
├── dataAgreements.json
├── dataDomains.json
├── dataModels.json
├── lexicon.json
├── notifications.json
├── reference.json
└── theme.json
```

## 📁 **Migrating from Local Files**

### **Automatic Migration**
Use the provided migration script:

```bash
cd api
python migrate_to_s3.py
```

This script will:
- Read all JSON files from your local `_data` directory
- Upload them to your S3 bucket
- Verify the migration was successful

### **Manual Migration**
If you prefer to upload manually:

```bash
# Using AWS CLI
aws s3 cp _data/ s3://your-bucket/ --recursive --exclude "*" --include "*.json"

# Or upload individual files
aws s3 cp _data/dataModels.json s3://your-bucket/dataModels.json
aws s3 cp _data/dataAgreements.json s3://your-bucket/dataAgreements.json
# ... etc
```

## 🚀 **Running the API**

### **Start with S3 Mode**
```bash
cd api
python run.py
```

The API will automatically detect S3 mode and read from your S3 bucket.

### **Check Current Mode**
The API will log which mode it's running in:
```
INFO - S3 MODE - Using S3 bucket: your-data-catalog-bucket
INFO - S3 client initialized with explicit credentials
```

## 🔍 **Verifying S3 Integration**

### **1. Check API Status**
```bash
curl http://localhost:8000/status
```

### **2. Test Data Endpoints**
```bash
# Test reading data models
curl http://localhost:8000/api/data/models

# Test reading agreements
curl http://localhost:8000/api/data/agreements
```

### **3. Check Logs**
Look for S3-related log messages:
```
INFO - Reading from S3: dataModels.json
INFO - Successfully read JSON file from S3: dataModels.json
```

## 🛠️ **Troubleshooting**

### **Common Issues**

#### **1. S3 Service Not Available**
```
ERROR - S3 service not available. Check your AWS credentials.
```

**Solutions:**
- Verify AWS credentials are set correctly
- Check if S3_BUCKET_NAME is set
- Ensure bucket exists and is accessible

#### **2. Access Denied**
```
ERROR - S3 error reading dataModels.json: An error occurred (AccessDenied)
```

**Solutions:**
- Check IAM permissions for S3 access
- Verify bucket policy allows read/write
- Ensure access key has proper permissions

#### **3. Bucket Not Found**
```
ERROR - S3 error reading dataModels.json: An error occurred (NoSuchBucket)
```

**Solutions:**
- Verify bucket name is correct
- Check if bucket exists in the specified region
- Ensure region matches bucket location

### **Debug Mode**
Enable debug logging:
```bash
LOG_LEVEL=DEBUG python run.py
```

## 🔄 **Switching Between Modes**

### **To S3 Mode**
```bash
export S3_MODE=true
export S3_BUCKET_NAME=your-bucket
python run.py
```

### **To Local Mode**
```bash
export TEST_MODE=true
unset S3_MODE
python run.py
```

### **To GitHub Mode**
```bash
unset S3_MODE
unset TEST_MODE
python run.py
```

## 📊 **Performance Considerations**

### **S3 Benefits**
- **Scalability**: Handle large datasets
- **Reliability**: 99.99% availability
- **Cost-effective**: Pay per request
- **Global access**: CDN integration possible

### **Optimization Tips**
- Use CloudFront for frequently accessed data
- Implement caching strategies
- Consider S3 Intelligent Tiering for cost optimization

## 🔒 **Security Best Practices**

### **IAM Permissions**
Minimal required permissions:
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
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket",
                "arn:aws:s3:::your-bucket/*"
            ]
        }
    ]
}
```

### **Bucket Policy**
Restrict access to your application:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowAppAccess",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::YOUR-ACCOUNT:user/YOUR-USER"
            },
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::your-bucket/*"
        }
    ]
}
```

## 📞 **Support**

If you encounter issues:
1. Check the logs for error messages
2. Verify your AWS configuration
3. Test S3 access with AWS CLI
4. Review IAM permissions and bucket policies

## 🔄 **Migration Checklist**

- [ ] Install boto3 dependency
- [ ] Set up AWS credentials
- [ ] Create S3 bucket
- [ ] Configure environment variables
- [ ] Run migration script
- [ ] Test API endpoints
- [ ] Verify S3 integration
- [ ] Update deployment scripts
- [ ] Monitor performance and costs

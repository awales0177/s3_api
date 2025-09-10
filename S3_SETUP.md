# S3 Backend Setup Guide

This guide will help you set up your API to use Amazon S3 as the backend data store instead of local files.

## Prerequisites

1. **AWS Account**: You need an AWS account with S3 access
2. **S3 Bucket**: Create an S3 bucket to store your JSON data files
3. **AWS Credentials**: Either IAM user credentials or IAM role with S3 permissions

## Step 1: Create S3 Bucket

1. Log into AWS Console
2. Navigate to S3 service
3. Click "Create bucket"
4. Choose a unique bucket name (e.g., `my-catalog-api-data`)
5. Select your preferred region
6. Configure bucket settings as needed
7. Create the bucket

## Step 2: Set Up AWS Credentials

### Option A: IAM User (Recommended for development)

1. Go to IAM service in AWS Console
2. Create a new user (e.g., `catalog-api-s3-user`)
3. Attach the policy `AmazonS3FullAccess` or create a custom policy with these permissions:
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
                   "arn:aws:s3:::your-bucket-name",
                   "arn:aws:s3:::your-bucket-name/*"
               ]
           }
       ]
   }
   ```
4. Create access keys for the user
5. Download the credentials

### Option B: IAM Role (Recommended for production)

1. Create an IAM role with S3 permissions
2. Attach the role to your EC2 instance or Lambda function
3. No need to store credentials in environment variables

## Step 3: Configure Environment Variables

1. Copy `env.example` to `.env`:
   ```bash
   cp env.example .env
   ```

2. Edit `.env` with your S3 configuration:
   ```bash
   # Enable S3 mode
   S3_MODE=true
   
   # Your S3 bucket name (just the name, no path)
   S3_BUCKET_NAME=your-bucket-name
   
   # AWS region where your bucket is located
   AWS_REGION=us-east-1
   
   # AWS credentials (only needed if not using IAM role)
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret-key
   ```

## Step 4: Test S3 Connection

Run the S3 connection test:

```bash
python test_s3_connection.py
```

This will:
- Verify your AWS credentials
- Test S3 read/write operations
- Verify DataService integration

## Step 5: Migrate Data to S3

If you have existing data in the `_data` folder, migrate it to S3:

```bash
python migrate_to_s3.py
```

This will:
- Upload all JSON files from `_data/` to your S3 bucket
- Preserve the file structure
- Verify the migration was successful

## Step 6: Start the API

Start your API server:

```bash
python main.py
```

The API will now use S3 as the backend data store.

## Verification

### Check S3 Status

Visit the debug endpoint to verify S3 is working:

```bash
curl http://localhost:8000/api/debug/s3
```

Expected response:
```json
{
    "s3_mode": true,
    "s3_available": true,
    "bucket_name": "your-bucket-name",
    "aws_region": "us-east-1",
    "message": "S3 is available"
}
```

### Test API Endpoints

Test that your API endpoints work with S3:

```bash
# Get all models
curl http://localhost:8000/api/models

# Get all agreements
curl http://localhost:8000/api/dataAgreements

# Get search stats
curl http://localhost:8000/api/search/stats
```

## Troubleshooting

### Common Issues

1. **"S3 service not available"**
   - Check your AWS credentials
   - Verify the bucket name is correct
   - Ensure the bucket exists in the specified region

2. **"Access Denied" errors**
   - Check IAM permissions
   - Verify the bucket policy allows your user/role

3. **"NoSuchKey" errors**
   - Run the migration script to upload data to S3
   - Check that files exist in the bucket

4. **"Invalid JSON" errors**
   - Verify the files were uploaded correctly
   - Check file encoding (should be UTF-8)

### Debug Commands

```bash
# Check S3 connection
python test_s3_connection.py

# Check API configuration
curl http://localhost:8000/api/debug/cache

# Check S3 status
curl http://localhost:8000/api/debug/s3

# List files in S3 bucket
aws s3 ls s3://your-bucket-name/
```

## Data Structure in S3

Your S3 bucket will contain JSON files in this structure:

```
your-bucket-name/
├── applications.json
├── dataAgreements.json
├── dataDomains.json
├── dataModels.json
├── dataPolicies.json
├── lexicon.json
├── notifications.json
├── reference.json
├── theme.json
└── toolkit.json
```

## Performance Considerations

- **S3 is eventually consistent**: Changes may take a few seconds to propagate
- **Request costs**: Each API call reads from S3 (consider caching for high-traffic scenarios)
- **Latency**: S3 adds ~100-200ms latency compared to local files
- **Bandwidth**: Consider CloudFront for global distribution

## Security Best Practices

1. **Use IAM roles** instead of access keys when possible
2. **Restrict S3 permissions** to only what's needed
3. **Enable S3 bucket versioning** for data protection
4. **Use S3 bucket policies** to restrict access by IP if needed
5. **Enable S3 access logging** for audit trails

## Monitoring

Monitor your S3 usage:

1. **CloudWatch metrics**: Track request counts and errors
2. **S3 access logs**: Monitor API access patterns
3. **Cost monitoring**: Track S3 storage and request costs
4. **API logs**: Monitor application-level errors

## Backup and Recovery

1. **Enable S3 versioning** to keep file history
2. **Set up S3 lifecycle policies** for cost optimization
3. **Cross-region replication** for disaster recovery
4. **Regular backups** to another S3 bucket or region

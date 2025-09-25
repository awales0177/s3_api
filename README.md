# S3 Data Catalog API

A FastAPI-based API for serving and managing catalog JSON files with S3 backend storage, full-text search, and comprehensive data management capabilities.

## 🚀 Features

- **S3 Backend Storage**: All data stored in Amazon S3 for scalability and reliability
- **Full-Text Search**: Advanced search capabilities across all data types
- **Real-time Reindexing**: Automatic search index updates when data changes
- **JWT Authentication**: Secure authentication with role-based access control
- **RESTful API**: Complete CRUD operations for all data types
- **IRSA Support**: IAM Roles for Service Accounts for secure Kubernetes deployments
- **Performance Monitoring**: Built-in metrics and response time tracking
- **CORS Support**: Cross-origin request handling
- **OpenAPI Documentation**: Automatic API documentation at `/docs`

## 🎯 Data Sources

### S3 Mode (Default)
- **Purpose**: Production-ready scalable data storage
- **Data Source**: Amazon S3 bucket with configurable folder prefix
- **Performance**: Fast, reliable, and scalable
- **Use Case**: Production environments, high-traffic applications

## 🛠️ Quick Start

### Prerequisites
- Python 3.8+
- AWS S3 bucket and credentials (or IRSA for Kubernetes)
- Required packages (see `requirements.txt`)

### Installation
```bash
git clone <repository-url>
cd s3_api
pip install -r requirements.txt
```

### Configuration

1. **Copy environment template:**
```bash
cp env.example .env
```

2. **Configure S3 settings in `.env`:**
```bash
# S3 Configuration
S3_MODE=true
S3_BUCKET_NAME=your-bucket-name
S3_FOLDER_PREFIX=dh-api
AWS_REGION=us-east-1

# AWS Credentials (choose one method):
# Method 1: IRSA (IAM Roles for Service Accounts) - Recommended for Kubernetes
# Leave these empty when using IRSA - the container will automatically assume the IAM role
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=

# Method 2: Explicit credentials (for local development or non-IRSA environments)
# AWS_ACCESS_KEY_ID=your-access-key
# AWS_SECRET_ACCESS_KEY=your-secret-key

# Server Configuration
PORT=8000
HOST=0.0.0.0
LOG_LEVEL=INFO
```

3. **Migrate data to S3 (first time only):**
```bash
python migrate_to_s3.py
```

### Running the API

```bash
python main.py
```

The API will be available at `http://localhost:8000`

## 📡 API Endpoints

### Data Endpoints
- `GET /api/{file_name}` - Get JSON file content
- `GET /api/{file_name}/paginated` - Get paginated content
- `GET /api/count/{file_name}` - Get item count

### Search Endpoints
- `GET /api/search` - Global search across all data
- `GET /api/search/suggest` - Get search suggestions
- `GET /api/search/stats` - Get search index statistics

### CRUD Endpoints (for each data type)
- `POST /api/{type}` - Create new item
- `PUT /api/{type}/{id}` - Update existing item
- `DELETE /api/{type}/{id}` - Delete item

### Debug Endpoints
- `GET /api/debug/s3` - S3 connection status
- `GET /api/debug/performance` - Performance metrics

## 🔍 Search Functionality

### Global Search
```bash
# Search across all data
curl "http://localhost:8000/api/search?q=customer&limit=10"

# Search with filters
curl "http://localhost:8000/api/search?q=model&types=models,domains&limit=5"
```

### Search Suggestions
```bash
# Get search suggestions
curl "http://localhost:8000/api/search/suggest?q=cust"
```

## 🐳 Docker Deployment

### Development
```bash
# Build and run with .env file
docker build -t s3-api:dev .
docker run -p 8000:8000 s3-api:dev
```

### Production
```bash
# Build without .env file (uses environment variables)
docker build -t s3-api:prod .
docker run -p 8000:8000 s3-api:prod
```

## ☸️ Kubernetes Deployment

### IRSA Setup (Recommended)

1. **Create IAM Role** with S3 permissions for your EKS cluster
2. **Apply Kubernetes manifests:**
```bash
kubectl apply -f k8s-configmap.yaml
kubectl apply -f k8s-deployment.yaml
```

3. **Update the service account annotation** with your IAM role ARN:
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: s3-api-service-account
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::YOUR_ACCOUNT_ID:role/YOUR_IAM_ROLE_NAME
```

### Required IAM Permissions
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
        "arn:aws:s3:::your-bucket-name",
        "arn:aws:s3:::your-bucket-name/*"
      ]
    }
  ]
}
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `S3_MODE` | `true` | Enable S3 backend storage |
| `S3_BUCKET_NAME` | Required | S3 bucket name |
| `S3_FOLDER_PREFIX` | `dh-api` | Folder prefix in S3 bucket |
| `AWS_REGION` | `us-east-1` | AWS region |
| `AWS_ACCESS_KEY_ID` | Optional | AWS access key (empty for IRSA) |
| `AWS_SECRET_ACCESS_KEY` | Optional | AWS secret key (empty for IRSA) |
| `HOST` | `0.0.0.0` | API server host |
| `PORT` | `8000` | API server port |
| `LOG_LEVEL` | `INFO` | Logging level |

### Data Files

The API manages the following JSON files in S3:

- `dataModels.json` - Data model definitions
- `dataAgreements.json` - Product agreements
- `dataDomains.json` - Data domains
- `applications.json` - Application information
- `dataPolicies.json` - Data policies
- `lexicon.json` - Business glossary
- `reference.json` - Reference data sets
- `toolkit.json` - Toolkit components

## 🔄 Automatic Reindexing

The search index automatically updates when data changes:

- **Model changes** → Reindexes `dataModels.json`
- **Agreement changes** → Reindexes `dataAgreements.json`
- **Domain changes** → Reindexes `dataDomains.json`
- **Application changes** → Reindexes `applications.json`
- **Policy changes** → Reindexes `dataPolicies.json`
- **Reference changes** → Reindexes `reference.json`
- **Toolkit changes** → Reindexes `toolkit.json`

### Manual Reindexing

```bash
# Reindex all files
curl -X POST "http://localhost:8000/api/admin/reindex"

# Reindex specific file
curl -X POST "http://localhost:8000/api/admin/reindex?file_name=dataModels.json"
```

## 🔐 Authentication

Currently, authentication is bypassed for development. To enable:

1. Set `AUTH_BYPASS=false` in `.env`
2. Configure JWT settings
3. Use login endpoint to get tokens

### Example Authentication Flow

```bash
# Login
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "pass"}'

# Use token in requests
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/models"
```

## 📊 Performance

### S3 Mode Performance
- **Startup Time**: ~2-3 seconds (includes S3 connection + search indexing)
- **Response Time**: ~50-200ms (depends on S3 latency)
- **Memory Usage**: ~200-300MB (includes search index)
- **Network**: S3 requests for data operations

### Search Performance
- **Index Build Time**: ~1-2 seconds (62 documents)
- **Search Response**: ~10-50ms
- **Index Size**: ~1,860 tokens across 62 documents

## 🐛 Troubleshooting

### Common Issues

**1. S3 Connection Failed**
```bash
# Check S3 configuration
curl http://localhost:8000/api/debug/s3

# Verify AWS credentials
aws s3 ls s3://your-bucket-name/
```

**2. Search Index Empty**
```bash
# Check search stats
curl http://localhost:8000/api/search/stats

# Manually reindex
curl -X POST http://localhost:8000/api/admin/reindex
```

**3. Port Already in Use**
```bash
# Change port
export PORT=8001
python main.py
```

### Debug Information
```bash
# Check S3 status
curl http://localhost:8000/api/debug/s3

# Check performance metrics
curl http://localhost:8000/api/debug/performance

# Check search statistics
curl http://localhost:8000/api/search/stats
```

## 📝 Examples

### Python Client Example
```python
import requests

# Search for models
response = requests.get('http://localhost:8000/api/search?q=customer&types=models')
results = response.json()

# Create a new model
model_data = {
    "shortName": "CustomerModel",
    "name": "Customer Data Model",
    "description": "Model for customer data"
}
response = requests.post('http://localhost:8000/api/models', json=model_data)
```

### JavaScript Client Example
```javascript
// Search across all data
const response = await fetch('http://localhost:8000/api/search?q=customer');
const results = await response.json();

// Get search suggestions
const suggestions = await fetch('http://localhost:8000/api/search/suggest?q=cust');
const suggestionsData = await suggestions.json();
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with S3 backend
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.
# Data Catalog API

A FastAPI-based API for serving and managing catalog JSON files with S3 backend storage, full-text search, and comprehensive data management capabilities.

## 🚀 Features

- **S3 Backend Storage**: All data stored in Amazon S3 for scalability and reliability
- **Full-Text Search**: Advanced search capabilities across all data types
- **Real-time Reindexing**: Automatic search index updates when data changes
- **JWT Authentication**: Secure authentication with role-based access control
- **RESTful API**: Complete CRUD operations for all data types
- **Performance Monitoring**: Built-in metrics and response time tracking
- **CORS Support**: Cross-origin request handling
- **OpenAPI Documentation**: Automatic API documentation at `/docs`

## 🎯 Data Sources

### S3 Mode (Default)
- **Purpose**: Production-ready scalable data storage
- **Data Source**: Amazon S3 bucket
- **Performance**: Fast, reliable, and scalable
- **Use Case**: Production environments, high-traffic applications

### Local Mode (Development)
- **Purpose**: Development and testing without S3 dependencies
- **Data Source**: Local `_data` directory
- **Performance**: Fastest response times, no network latency
- **Use Case**: Local development, offline testing

## 🛠️ Quick Start

### Prerequisites
- Python 3.8+
- AWS S3 bucket and credentials
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
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Authentication (currently bypassed for development)
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

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
- `GET /api/search/suggestions` - Get search suggestions
- `GET /api/search/stats` - Get search index statistics

### Model Management
- `GET /api/models` - List all data models
- `GET /api/models/{short_name}` - Get specific model
- `POST /api/models` - Create new model
- `PUT /api/models/{short_name}` - Update model
- `DELETE /api/models/{short_name}` - Delete model

### Agreement Management
- `GET /api/agreements` - List all agreements
- `GET /api/agreements/{agreement_id}` - Get specific agreement
- `POST /api/agreements` - Create new agreement
- `PUT /api/agreements/{agreement_id}` - Update agreement
- `DELETE /api/agreements/{agreement_id}` - Delete agreement

### Domain Management
- `GET /api/domains` - List all domains
- `GET /api/domains/{domain_id}` - Get specific domain
- `POST /api/domains` - Create new domain
- `PUT /api/domains/{domain_id}` - Update domain
- `DELETE /api/domains/{domain_id}` - Delete domain

### Application Management
- `GET /api/applications` - List all applications
- `GET /api/applications/{application_id}` - Get specific application
- `POST /api/applications` - Create new application
- `PUT /api/applications/{application_id}` - Update application
- `DELETE /api/applications/{application_id}` - Delete application

### Policy Management
- `GET /api/policies` - List all policies
- `GET /api/policies/{policy_id}` - Get specific policy
- `POST /api/policies` - Create new policy
- `PUT /api/policies/{policy_id}` - Update policy
- `DELETE /api/policies/{policy_id}` - Delete policy

### Reference Data Management
- `GET /api/reference` - List all reference data
- `GET /api/reference/{item_id}` - Get specific reference item
- `POST /api/reference` - Create new reference item
- `PUT /api/reference/{item_id}` - Update reference item
- `DELETE /api/reference/{item_id}` - Delete reference item

### Toolkit Management
- `GET /api/toolkit/{component_type}` - List toolkit components by type
- `GET /api/toolkit/{component_type}/{component_id}` - Get specific component
- `POST /api/toolkit/{component_type}` - Create new component
- `PUT /api/toolkit/{component_type}/{component_id}` - Update component
- `DELETE /api/toolkit/{component_type}/{component_id}` - Delete component

### Authentication Endpoints
- `POST /api/auth/login` - User login
- `POST /api/auth/register` - User registration
- `GET /api/auth/me` - Get current user info
- `POST /api/auth/refresh` - Refresh JWT token

### Admin Endpoints
- `POST /api/admin/reindex` - Manually trigger search reindexing
- `GET /api/admin/reindex?file_name={filename}` - Reindex specific file

### Debug Endpoints
- `GET /api/debug/s3` - S3 connection status
- `GET /api/debug/performance` - Performance metrics
- `GET /api/debug/cache` - Cache status (S3 mode)

## 🔍 Search Functionality

### Global Search
```bash
# Search across all data
curl "http://localhost:8000/api/search?q=customer&limit=10"

# Search with filters
curl "http://localhost:8000/api/search?q=model&doc_types=models,domains&limit=5"
```

### Search Suggestions
```bash
# Get search suggestions
curl "http://localhost:8000/api/search/suggestions?q=cust"
```

### Search Statistics
```bash
# Get search index stats
curl "http://localhost:8000/api/search/stats"
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `S3_MODE` | `true` | Enable S3 backend storage |
| `S3_BUCKET_NAME` | Required | S3 bucket name |
| `AWS_REGION` | `us-east-1` | AWS region |
| `AWS_ACCESS_KEY_ID` | Required | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | Required | AWS secret key |
| `JWT_SECRET_KEY` | Required | JWT signing key |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_EXPIRATION_HOURS` | `24` | JWT expiration time |
| `PORT` | `8000` | API server port |
| `HOST` | `0.0.0.0` | API server host |
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
aws s3 ls s3://your-bucket-name
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

**4. Data Not Found**
```bash
# Check if data exists in S3
aws s3 ls s3://your-bucket-name/

# Migrate data if needed
python migrate_to_s3.py
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

## 🚀 Production Deployment

### Environment Setup
1. Set up AWS S3 bucket
2. Configure IAM permissions
3. Set production environment variables
4. Enable authentication
5. Set up monitoring and logging

### Docker Deployment
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### Health Checks
```bash
# API health
curl http://localhost:8000/api/debug/s3

# Search health
curl http://localhost:8000/api/search/stats
```

## 📝 Examples

### Python Client Example
```python
import requests

# Search for models
response = requests.get('http://localhost:8000/api/search?q=customer&doc_types=models')
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
const suggestions = await fetch('http://localhost:8000/api/search/suggestions?q=cust');
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
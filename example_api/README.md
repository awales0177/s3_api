# Data Catalog API

A FastAPI-based API for serving and managing catalog JSON files with support for multiple data sources and caching strategies.

## 🚀 Features

- **Multiple Data Sources**: GitHub, local files, or cached GitHub data
- **Smart Caching**: Configurable cache duration with automatic cleanup
- **Performance Monitoring**: Built-in metrics and response time tracking
- **Flexible Modes**: Test, passthrough, and cached modes
- **Authentication**: Basic HTTP authentication for admin endpoints
- **CORS Support**: Cross-origin request handling
- **OpenAPI Documentation**: Automatic API documentation at `/docs`

## 🎯 API Modes

### 1. 🧪 Test Mode
- **Purpose**: Development and testing without network dependencies
- **Data Source**: Local `_data` directory
- **Performance**: Fastest response times, no network latency
- **Use Case**: Local development, offline testing, CI/CD pipelines

### 2. 🌐 Passthrough Mode
- **Purpose**: Real-time data from GitHub
- **Data Source**: GitHub raw content (no caching)
- **Performance**: Slower but always up-to-date
- **Use Case**: Development with live data, testing GitHub integration

### 3. 💾 Cached Mode (Default)
- **Purpose**: Production use with optimal performance
- **Data Source**: GitHub with intelligent caching
- **Performance**: Fast after initial load, automatic cache management
- **Use Case**: Production environments, high-traffic applications

## 🛠️ Quick Start

### Prerequisites
- Python 3.8+
- Required packages (see `requirements.txt`)

### Installation
```bash
cd api
pip install -r requirements.txt
```

### Running the API

#### Option 1: Interactive Runner (Recommended)
```bash
python run.py
```
Choose your mode from the interactive menu.

#### Option 2: Direct Mode Selection

**Test Mode (Local Data):**
```bash
# Unix/Linux/macOS
./run_test.sh

# Windows
run_test.bat

# Or manually
export TEST_MODE=true
export PASSTHROUGH_MODE=false
python main.py
```

**Passthrough Mode (Direct GitHub):**
```bash
export TEST_MODE=false
export PASSTHROUGH_MODE=true
python main.py
```

**Cached Mode (Default):**
```bash
export TEST_MODE=false
export PASSTHROUGH_MODE=false
python main.py
```

#### Option 3: Environment Variables
Create a `.env` file:
```bash
TEST_MODE=true
PASSTHROUGH_MODE=false
PORT=8000
CACHE_DURATION_MINUTES=15
LOG_LEVEL=INFO
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TEST_MODE` | `false` | Enable test mode (local data) |
| `PASSTHROUGH_MODE` | `false` | Enable passthrough mode (no cache) |
| `GITHUB_RAW_BASE_URL` | GitHub URL | Base URL for GitHub raw content |
| `CACHE_DURATION_MINUTES` | `15` | Cache duration in minutes |
| `PORT` | `8000` | API server port |
| `HOST` | `0.0.0.0` | API server host |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ADMIN_USERNAME` | `admin` | Admin username |
| `ADMIN_PASSWORD` | `admin` | Admin password |

### Data Files

The API serves data from the following JSON files in the `_data` directory:

- `dataModels.json` - Data model definitions
- `dataAgreements.json` - Product agreements
- `dataDomains.json` - Data domains
- `applications.json` - Application information
- `lexicon.json` - Business glossary
- `reference.json` - Reference data sets
- `theme.json` - UI theme configuration

## 📡 API Endpoints

### Data Endpoints
- `GET /api/{file_name}` - Get JSON file content
- `GET /api/{file_name}/paginated` - Get paginated content
- `GET /api/count/{file_name}` - Get item count

### Debug Endpoints
- `GET /api/debug/mode` - Get current API mode
- `GET /api/debug/cache` - Get cache status
- `GET /api/debug/performance` - Get performance metrics

### Admin Endpoints (Authentication Required)
- `POST /api/admin/update` - Update data files
- `GET /api/admin/files` - List available files

## 🔍 Testing the API

### Check Current Mode
```bash
curl http://localhost:8000/api/debug/mode
```

### Test Local Data (Test Mode)
```bash
# Start in test mode
export TEST_MODE=true
python main.py

# In another terminal
curl http://localhost:8000/api/domains
```

### Test GitHub Data (Passthrough Mode)
```bash
# Start in passthrough mode
export PASSTHROUGH_MODE=true
python main.py

# In another terminal
curl http://localhost:8000/api/domains
```

## 📊 Performance

### Test Mode Performance
- **Startup Time**: ~100ms
- **Response Time**: ~5-20ms
- **Memory Usage**: ~50-100MB
- **Network**: None

### Cached Mode Performance
- **Startup Time**: ~200ms
- **Response Time**: ~10-50ms (first), ~5-20ms (cached)
- **Memory Usage**: ~100-200MB
- **Network**: Initial GitHub requests

### Passthrough Mode Performance
- **Startup Time**: ~150ms
- **Response Time**: ~100-500ms (depends on GitHub)
- **Memory Usage**: ~80-150MB
- **Network**: Every request

## 🐛 Troubleshooting

### Common Issues

**1. Port Already in Use**
```bash
# Change port
export PORT=8001
python main.py
```

**2. Local Data Files Not Found**
```bash
# Ensure _data directory exists
ls -la _data/
```

**3. GitHub Rate Limiting**
```bash
# Switch to test mode
export TEST_MODE=true
python main.py
```

**4. Cache Issues**
```bash
# Clear cache by restarting or check debug endpoint
curl http://localhost:8000/api/debug/cache
```

### Debug Information
```bash
# Check API mode
curl http://localhost:8000/api/debug/mode

# Check cache status
curl http://localhost:8000/api/debug/cache

# Check performance metrics
curl http://localhost:8000/api/debug/performance
```

## 🔄 Development Workflow

### 1. Local Development (Test Mode)
```bash
export TEST_MODE=true
python main.py
```
- Fast iteration
- No network dependencies
- Use local `_data` files

### 2. Testing GitHub Integration (Passthrough Mode)
```bash
export PASSTHROUGH_MODE=true
python main.py
```
- Test GitHub connectivity
- Verify data freshness
- Debug network issues

### 3. Production Testing (Cached Mode)
```bash
export TEST_MODE=false
export PASSTHROUGH_MODE=false
python main.py
```
- Test caching behavior
- Performance testing
- Production simulation

## 📝 Examples

### Python Client Example
```python
import requests

# Test mode - local data
response = requests.get('http://localhost:8000/api/domains')
domains = response.json()

# Check mode
mode = requests.get('http://localhost:8000/api/debug/mode').json()
print(f"API Mode: {mode['mode_description']}")
```

### JavaScript Client Example
```javascript
// Test mode - local data
const response = await fetch('http://localhost:8000/api/domains');
const domains = await response.json();

// Check mode
const mode = await fetch('http://localhost:8000/api/debug/mode').json();
console.log(`API Mode: ${mode.mode_description}`);
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test in all modes
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

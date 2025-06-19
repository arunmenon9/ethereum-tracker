
Ethereum Transaction Tracker API
================================

A production-ready FastAPI application for tracking and analyzing Ethereum wallet transactions with comprehensive reporting capabilities.

🚀 Features
-----------

### Core Functionality

-   **Multi-Transaction Type Support**: ETH transfers, ERC-20 tokens, ERC-721 NFTs, ERC-1155 tokens, and internal transactions
-   **Advanced Filtering**: Filter by date range, transaction types, value ranges
-   **Comprehensive Analytics**: Usage statistics, wallet analytics, trending data
-   **CSV Export**: Direct CSV export for smaller datasets
-   **Report Generation**: Background report generation for large datasets using block range segmentation
-   **Redis Caching**: Intelligent caching system to minimize API calls and improve performance

### Production Features

-   **Docker Containerization**: Complete Docker Compose setup with PostgreSQL and Redis
-   **API Authentication**: Bearer token authentication
-   **Rate Limiting**: Built-in rate limiting and request tracking
-   **Health Monitoring**: Health check endpoints for monitoring
-   **Structured Logging**: Comprehensive logging with request tracking
-   **Error Handling**: Detailed error responses with validation

### API Endpoints

-   `GET /api/v1/transactions/{wallet_address}` - Get paginated transactions
-   `GET /api/v1/transactions/{wallet_address}/summary` - Get transaction summary
-   `GET /api/v1/exports/csv` - Export transactions to CSV
-   `GET /api/v1/reports/generate` - Generate comprehensive reports for large datasets
-   `GET /api/v1/reports/status/{wallet_address}` - Check report generation status
-   `GET /api/v1/reports/download/{wallet_address}` - Download completed reports
-   `GET /api/v1/analytics/overview` - Get analytics overview
-   `DELETE /api/v1/cache/clear` - Clear all cached data

🛠 Tech Stack
-------------

-   **FastAPI**: High-performance Python web framework
-   **PostgreSQL**: Primary database for storing transactions and metadata
-   **Redis**: Caching layer for API responses and session management
-   **Etherscan API**: Data source for Ethereum blockchain data
-   **Docker & Docker Compose**: Containerization and orchestration
-   **Pydantic**: Data validation and settings management

📋 Prerequisites
----------------

-   Docker and Docker Compose installed
-   Etherscan API key (free tier available)

🚀 Quick Start
--------------

### 1\. Clone the Repository

bash

```
git clone <repository-url>
cd ethereum-transaction-tracker
```

### 2\. Environment Setup

Create a `.env` file in the root directory:

env

```
# Database
POSTGRES_PASSWORD=your_secure_password

# Etherscan API
ETHERSCAN_API_KEY=your_etherscan_api_key

# Authentication
API_KEY=your-secret-api-key
SECRET_KEY=your-secret-key

# Optional: Redis URL (uses default if not specified)
REDIS_URL=redis://redis:6379/0
```

### 3\. Get Your Etherscan API Key

1.  Visit [Etherscan.io](https://etherscan.io/apis)
2.  Create a free account
3.  Generate an API key
4.  Add it to your `.env` file

### 4\. Start the Application

bash

```
# Build and start all services
docker-compose up --build

# Or run in detached mode
docker-compose up -d --build
```

### 5\. Verify Installation

-   **API Documentation**: <http://localhost:8000/docs>
-   **Health Check**: <http://localhost:8000/health>
-   **Alternative Docs**: <http://localhost:8000/redoc>

📖 Usage Examples
-----------------

### Authentication

All API requests require a Bearer token:

bash

```
curl -H "Authorization: Bearer your-secret-api-key"\
     http://localhost:8000/api/v1/transactions/0x742d35Cc63aB4747B8bc21bB6c2d65bb0E4e8b5d
```

### Get Wallet Transactions

bash

```
# Basic request
curl -H "Authorization: Bearer your-api-key"\
     "http://localhost:8000/api/v1/transactions/0x742d35Cc63aB4747B8bc21bB6c2d65bb0E4e8b5d"

# With filters
curl -H "Authorization: Bearer your-api-key"\
     "http://localhost:8000/api/v1/transactions/0x742d35Cc63aB4747B8bc21bB6c2d65bb0E4e8b5d?start_date=2024-01-01T00:00:00&transaction_types=ETH&transaction_types=ERC-20"
```

### Export to CSV

bash

```
curl -X POST -H "Authorization: Bearer your-api-key"\
     -H "Content-Type: application/json"\
     -d '{"wallet_address": "0x742d35Cc63aB4747B8bc21bB6c2d65bb0E4e8b5d"}'\
     http://localhost:8000/api/v1/exports/csv --output transactions.csv
```

### Generate Report for Large Datasets

bash

```
# Start report generation
curl -X POST -H "Authorization: Bearer your-api-key"\
     -H "Content-Type: application/json"\
     -d '{"wallet_address": "0x742d35Cc63aB4747B8bc21bB6c2d65bb0E4e8b5d"}'\
     http://localhost:8000/api/v1/reports/generate

# Check status
curl -H "Authorization: Bearer your-api-key"\
     http://localhost:8000/api/v1/reports/status/0x742d35Cc63aB4747B8bc21bB6c2d65bb0E4e8b5d

# Download when complete
curl -H "Authorization: Bearer your-api-key"\
     http://localhost:8000/api/v1/reports/download/0x742d35Cc63aB4747B8bc21bB6c2d65bb0E4e8b5d\
     --output large_dataset_report.csv
```

🏗 Architecture
---------------

### Database Schema

-   **blocks**: Block metadata
-   **transactions**: All transaction data with comprehensive indexing
-   **api_usage**: Request tracking and analytics
-   **report_jobs**: Background report generation tracking

### Caching Strategy

-   **Transaction data**: Cached with configurable TTL to reduce API calls [FastAPI in Containers - Docker - FastAPI](https://fastapi.tiangolo.com/deployment/docker/)
-   **Block data**: Cached for performance optimization
-   **Rate limiting**: Uses Redis for distributed rate limiting

### Error Handling

-   **Large Datasets**: Automatic detection and redirection to report generation
-   **Validation Errors**: Detailed field-level error messages
-   **API Limits**: Graceful handling of Etherscan rate limits with retry logic

🔧 Configuration
----------------

### Environment Variables

env

```
# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/ethereum_tracker

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# Etherscan API
ETHERSCAN_API_KEY=your_api_key
ETHERSCAN_RATE_LIMIT=5.0  # requests per second

# Application Security
API_KEY=your-secret-api-key
SECRET_KEY=your-secret-key

# Performance Tuning
CACHE_TTL_TRANSACTIONS=3600  # 1 hour
MAX_EXPORT_RECORDS=50000
EXPORT_BATCH_SIZE=1000

# Logging
LOG_LEVEL=INFO
DEBUG=false
```

### Docker Compose Services

-   **api**: FastAPI application server
-   **postgres**: PostgreSQL database with automatic schema initialization
-   **redis**: Redis cache server with persistence

🧪 Development
--------------

### Local Development Setup

bash

```
# Install Python dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env

# Start only database services
docker-compose up postgres redis -d

# Run API locally
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Database Operations

bash

```
# Access PostgreSQL directly
docker-compose exec postgres psql -U postgres -d ethereum_tracker

# View logs
docker-compose logs api
docker-compose logs postgres
```

### Testing

bash

```
# Run tests in container
docker-compose exec api pytest -v

# Run with coverage
docker-compose exec api coverage run -m pytest -v && coverage report
```

📊 Monitoring & Analytics
-------------------------

### Health Checks

The application includes comprehensive health checks:

-   Database connectivity
-   Redis connectivity
-   Service status monitoring

### Built-in Analytics

-   Request tracking per wallet address
-   Endpoint usage statistics


🔒 Security Considerations
--------------------------

-   **API Key Authentication**: Required for all endpoints
-   **Input Validation**: Comprehensive validation for Ethereum addresses and parameters
-   **Rate Limiting**: Built-in protection against abuse
-   **Environment Variables**: Secure configuration management
-   **Database Security**: Parameterized queries to prevent SQL injection

🚀 Production Deployment
------------------------

### Scaling Considerations

-   **Horizontal Scaling**: Multiple API containers behind a load balancer
-   **Database Optimization**: Connection pooling and query optimization
-   **Cache Strategy**: Distributed Redis caching
-   **Background Jobs**: Report generation runs in background threads


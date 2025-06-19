
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
# Etherscan API Configuration
ETHERSCAN_API_KEY=your_key

# Database Configuration
POSTGRES_PASSWORD=your_secure_postgres_password
DATABASE_URL=postgresql+asyncpg://postgres:your_secure_postgres_password@localhost:5432/ethereum_tracker

# Redis Configuration  
REDIS_URL=redis://localhost:6379/0

# API Authentication
API_KEY=your-secret-api-key
SECRET_KEY=your-secret-key-for-jwt

# Application Configuration
LOG_LEVEL=INFO
DEBUG=false
ALLOWED_HOSTS=["*"]

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
ETHERSCAN_RATE_LIMIT=5.0

# CSV Export Limits
MAX_EXPORT_RECORDS=50000
EXPORT_BATCH_SIZE=1000

# Cache TTL (seconds)
CACHE_TTL_TRANSACTIONS=3600
CACHE_TTL_BLOCKS=3600

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

🏗️ Architecture Decisions
--------------------------

### 1\. **Dual-Path Strategy for Dataset Sizes**

-   **Small datasets (<10k transactions)**: Direct API response with pagination
-   **Large datasets (>10k transactions)**: Background job processing with file generation
-   **Rationale**: Etherscan API has pagination limits (10k records max). Background jobs prevent timeouts and provide better UX for large datasets.

### 2\. **Block Range Segmentation**

For large datasets, we segment requests by block ranges rather than pagination:

python

```
# Instead of: page=1, page=2, page=3... (hits 10k limit)
# We use: blocks 0-100k, 100k-200k, 200k-300k...
```

This bypasses pagination limits and enables complete transaction history retrieval.

### 3\. **Multi-layer Caching Strategy**

-   **L1 Cache**: Redis for API responses (1-hour TTL)
-   **L2 Cache**: Database storage for processed transactions
-   **L3 Cache**: Etherscan rate limiting to prevent API exhaustion

### 4\. **Streaming CSV Generation**

Uses FastAPI's `StreamingResponse` to handle large CSV files without memory exhaustion:

python

```
async def generate_csv_data() -> AsyncIterator[str]:
    # Process and yield data in chunks
    yield csv_chunk
```

### 5\. **Comprehensive Transaction Type Support**

Handles all Ethereum transaction types through parallel API calls:

-   Normal transactions (ETH transfers)
-   Internal transactions (smart contract calls)
-   ERC-20 token transfers
-   ERC-721/ERC-1155 NFT transfers

⚠️ Assumptions and Limitations
------------------------------

### Authentication (POC Limitation)

-   **Current Implementation**: Simple Bearer token authentication with a single API key
-   **Production Recommendation**: Implement proper user management with JWT tokens, OAuth2, or similar
-   **Rationale**: For POC purposes, basic auth meets requirements while keeping implementation simple

### Analytics Design (Single-User Focus)

-   **Current Scope**: Analytics are wallet-centric, not user-centric
-   **Assumption**: Single user per deployment scenario
-   **Future Enhancement**: Multi-user analytics would require:

    sql

    ```
    -- Additional user management tables
    users (id, email, created_at)
    user_wallets (user_id, wallet_address, nickname)
    user_api_usage (user_id, wallet_address, endpoint, timestamp)
    ```

-   **Rationale**: Time constraints led to focusing on core transaction functionality first

### Data Consistency

-   **Assumption**: Etherscan data is the source of truth
-   **Limitation**: No cross-validation with other data sources
-   **Handling**: Graceful degradation when Etherscan is unavailable

### Rate Limiting

-   **Etherscan Free Tier**: 5 requests/second, 100k requests/day
-   **Current Strategy**: Conservative rate limiting with exponential backoff
-   **Scaling**: Consider Etherscan Pro plan for production

🔧 Configuration
----------------

### Docker Compose Services

-   **api**: FastAPI application server
-   **postgres**: PostgreSQL database with automatic schema initialization
-   **redis**: Redis cache server with persistence

🧪 Development
--------------

### Local Development Setup

bash

```
docker-compose up --build

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


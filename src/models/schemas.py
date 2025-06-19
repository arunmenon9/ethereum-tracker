from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from enum import Enum

class TransactionType(str, Enum):
    ETH = "ETH"
    ERC20 = "ERC-20"
    ERC721 = "ERC-721"
    ERC1155 = "ERC-1155"
    INTERNAL = "Internal"

class TransactionResponse(BaseModel):
    tx_hash: str = Field(..., description="Transaction hash")
    block_number: int = Field(..., description="Block number")
    timestamp: datetime = Field(..., description="Transaction timestamp")
    from_address: str = Field(..., description="Sender address")
    to_address: Optional[str] = Field(None, description="Recipient address")
    transaction_type: TransactionType = Field(..., description="Transaction type")
    token_address: Optional[str] = Field(None, description="Token contract address")
    token_symbol: Optional[str] = Field(None, description="Token symbol")
    token_name: Optional[str] = Field(None, description="Token name")
    token_id: Optional[str] = Field(None, description="NFT token ID")
    value: str = Field(..., description="Transaction value")
    gas_fee: str = Field(..., description="Gas fee in ETH")

class TransactionFilter(BaseModel):
    start_date: Optional[datetime] = Field(None, description="Start date filter")
    end_date: Optional[datetime] = Field(None, description="End date filter")
    transaction_types: Optional[List[TransactionType]] = Field(None, description="Filter by transaction types")
    min_value: Optional[Decimal] = Field(None, ge=0, description="Minimum value filter")
    max_value: Optional[Decimal] = Field(None, ge=0, description="Maximum value filter")
    
    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, v, info):
        if v and info.data.get('start_date') and v < info.data['start_date']:
            raise ValueError('end_date must be after start_date')
        return v

class TransactionListResponse(BaseModel):
    transactions: List[TransactionResponse]
    total_count: int
    page: int
    page_size: int
    has_more: bool

class CSVExportRequest(BaseModel):
    wallet_address: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$")
    filters: Optional[TransactionFilter] = Field(default_factory=TransactionFilter)
    
    @field_validator('wallet_address')
    @classmethod
    def validate_address(cls, v):
        return v.lower()

class ErrorResponse(BaseModel):
    error: bool = True
    message: str
    timestamp: str


class AnalyticsOverview(BaseModel):
    period: dict
    summary: dict
    top_endpoints: List[dict]
    top_wallets: List[dict]

class UsageStats(BaseModel):
    total_requests: int
    unique_wallets: int

class WalletStats(BaseModel):
    wallet_address: str
    statistics: dict
    endpoint_breakdown: List[dict]
    recent_activity: List[dict]

class EndpointStats(BaseModel):
    endpoint_statistics: List[dict]
    performance_trends: List[dict]

class TrendData(BaseModel):
    period: str
    granularity: str
    start_date: str
    end_date: str
    growth_rate_percent: float
    data: List[dict]

class RealTimeMetrics(BaseModel):
    timestamp: str
    metrics: dict

class ReportStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    FAILED = "failed"

class ReportRequest(BaseModel):
    wallet_address: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$")
    filters: Optional[TransactionFilter] = Field(default_factory=TransactionFilter)
    
    @field_validator('wallet_address')
    @classmethod
    def validate_address(cls, v):
        return v.lower()

class ReportStatusResponse(BaseModel):
    wallet_address: str
    status: ReportStatus
    created_at: datetime
    updated_at: datetime
    progress_percentage: Optional[int] = None
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None
    file_size_mb: Optional[float] = None
    total_transactions: Optional[int] = None

class ReportGenerationResponse(BaseModel):
    message: str
    wallet_address: str
    status: ReportStatus
    report_id: str
    status_endpoint: str
    estimated_time_minutes: Optional[int] = None



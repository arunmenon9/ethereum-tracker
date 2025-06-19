from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from datetime import datetime, timedelta

from src.services.analytics import AnalyticsService
from src.api.auth import verify_api_key
from src.models.schemas import AnalyticsOverview, TrendData, WalletStats, EndpointStats, RealTimeMetrics
from src.utils.validators import AddressValidator

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/overview", response_model=AnalyticsOverview)
async def get_analytics_overview(
    start_date: Optional[datetime] = Query(None, description="Start date for analytics period"),
    end_date: Optional[datetime] = Query(None, description="End date for analytics period"),
    api_key: str = Depends(verify_api_key)
):
    """
    Get comprehensive analytics overview
    
    Provides:
    - Total requests and unique wallets in period
    - Average response time and error rates
    - Top endpoints by usage
    - Most active wallet addresses
    """
    
    service = AnalyticsService()
    return await service.get_analytics_overview(start_date, end_date)

@router.get("/trends", response_model=TrendData)
async def get_usage_trends(
    period: str = Query("7d", regex="^(7d|30d|90d)$", description="Time period (7d, 30d, 90d)"),
    granularity: str = Query("daily", regex="^(hourly|daily)$", description="Data granularity"),
    api_key: str = Depends(verify_api_key)
):
    """
    Get usage trends over time
    
    Shows request patterns and growth trends:
    - Daily/hourly request counts
    - Unique wallet activity
    - Growth rate calculations
    - Trend visualization data
    """
    
    service = AnalyticsService()
    return await service.get_usage_trends(period, granularity)

@router.get("/wallets", response_model=dict)
async def get_wallet_analytics(
    wallet_address: Optional[str] = Query(None, description="Specific wallet address to analyze"),
    limit: int = Query(100, ge=1, le=1000, description="Number of top wallets to return"),
    api_key: str = Depends(verify_api_key)
):
    """
    Get wallet usage analytics
    
    For specific wallet:
    - Total requests and usage history
    - Endpoint usage breakdown
    - Recent activity log
    
    For all wallets:
    - Top wallets by activity
    - Usage statistics summary
    """
    
    if wallet_address:
        try:
            validated_address = AddressValidator.validate_ethereum_address(wallet_address)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        wallet_address = validated_address
    
    service = AnalyticsService()
    return await service.get_wallet_analytics(wallet_address, limit)

@router.get("/endpoints", response_model=EndpointStats)
async def get_endpoint_analytics(
    api_key: str = Depends(verify_api_key)
):
    """
    Get endpoint performance analytics
    
    Provides:
    - Request volume per endpoint
    - Response time statistics
    - Error rates by endpoint
    - Performance trends (24h)
    """
    
    service = AnalyticsService()
    return await service.get_endpoint_analytics()

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import text

from src.database import database
from src.models.schemas import AnalyticsOverview, UsageStats, WalletStats, EndpointStats, TrendData

logger = logging.getLogger(__name__)

class AnalyticsService:
    """Service for handling analytics and usage statistics"""
    
    async def get_analytics_overview(
        self, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get comprehensive analytics overview"""
        
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        # Get total requests
        total_requests_query = """
            SELECT COUNT(*) as total_requests
            FROM api_usage 
            WHERE request_timestamp BETWEEN :start_date AND :end_date
        """
        total_requests = await database.fetch_one(
            total_requests_query, 
            {"start_date": start_date, "end_date": end_date}
        )
        
        # Get unique wallets
        unique_wallets_query = """
            SELECT COUNT(DISTINCT wallet_address) as unique_wallets
            FROM api_usage 
            WHERE request_timestamp BETWEEN :start_date AND :end_date
        """
        unique_wallets = await database.fetch_one(
            unique_wallets_query,
            {"start_date": start_date, "end_date": end_date}
        )
        
        # Get average response time (if recorded)
        avg_response_time_query = """
            SELECT AVG(response_time_ms) as avg_response_time
            FROM api_usage 
            WHERE request_timestamp BETWEEN :start_date AND :end_date
            AND response_time_ms IS NOT NULL
        """
        avg_response_time = await database.fetch_one(
            avg_response_time_query,
            {"start_date": start_date, "end_date": end_date}
        )
        
        # Get top endpoints
        top_endpoints_query = """
            SELECT endpoint, COUNT(*) as request_count
            FROM api_usage 
            WHERE request_timestamp BETWEEN :start_date AND :end_date
            GROUP BY endpoint
            ORDER BY request_count DESC
            LIMIT 10
        """
        top_endpoints = await database.fetch_all(
            top_endpoints_query,
            {"start_date": start_date, "end_date": end_date}
        )
        
        # Get top wallets
        top_wallets_query = """
            SELECT wallet_address, COUNT(*) as request_count
            FROM api_usage 
            WHERE request_timestamp BETWEEN :start_date AND :end_date
            GROUP BY wallet_address
            ORDER BY request_count DESC
            LIMIT 10
        """
        top_wallets = await database.fetch_all(
            top_wallets_query,
            {"start_date": start_date, "end_date": end_date}
        )
        
        # Get error rate (if status codes are recorded)
        error_rate_query = """
            SELECT 
                COUNT(CASE WHEN status_code >= 400 THEN 1 END) * 100.0 / COUNT(*) as error_rate
            FROM api_usage 
            WHERE request_timestamp BETWEEN :start_date AND :end_date
            AND status_code IS NOT NULL
        """
        error_rate = await database.fetch_one(
            error_rate_query,
            {"start_date": start_date, "end_date": end_date}
        )
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "summary": {
                "total_requests": total_requests["total_requests"] if total_requests else 0,
                "unique_wallets": unique_wallets["unique_wallets"] if unique_wallets else 0,
                "avg_response_time_ms": float(avg_response_time["avg_response_time"]) if avg_response_time and avg_response_time["avg_response_time"] else None,
                "error_rate_percent": float(error_rate["error_rate"]) if error_rate and error_rate["error_rate"] else None
            },
            "top_endpoints": [
                {
                    "endpoint": row["endpoint"],
                    "request_count": row["request_count"]
                }
                for row in top_endpoints
            ],
            "top_wallets": [
                {
                    "wallet_address": row["wallet_address"],
                    "request_count": row["request_count"]
                }
                for row in top_wallets
            ]
        }
    
    async def get_usage_trends(
        self, 
        period: str = "7d",
        granularity: str = "daily"
    ) -> Dict[str, Any]:
        """Get usage trends over time"""
        
        # Parse period
        if period == "7d":
            start_date = datetime.utcnow() - timedelta(days=7)
            date_format = "%Y-%m-%d"
        elif period == "30d":
            start_date = datetime.utcnow() - timedelta(days=30)
            date_format = "%Y-%m-%d"
        elif period == "90d":
            start_date = datetime.utcnow() - timedelta(days=90)
            date_format = "%Y-%m-%d"
        else:
            start_date = datetime.utcnow() - timedelta(days=7)
            date_format = "%Y-%m-%d"
        
        end_date = datetime.utcnow()
        
        # Get daily usage trends
        if granularity == "daily":
            trends_query = """
                SELECT 
                    DATE(request_timestamp) as date,
                    COUNT(*) as request_count,
                    COUNT(DISTINCT wallet_address) as unique_wallets
                FROM api_usage 
                WHERE request_timestamp BETWEEN :start_date AND :end_date
                GROUP BY DATE(request_timestamp)
                ORDER BY date
            """
        else:  # hourly
            trends_query = """
                SELECT 
                    DATE_TRUNC('hour', request_timestamp) as date,
                    COUNT(*) as request_count,
                    COUNT(DISTINCT wallet_address) as unique_wallets
                FROM api_usage 
                WHERE request_timestamp BETWEEN :start_date AND :end_date
                GROUP BY DATE_TRUNC('hour', request_timestamp)
                ORDER BY date
            """
        
        trends = await database.fetch_all(
            trends_query,
            {"start_date": start_date, "end_date": end_date}
        )
        
        # Calculate growth rate
        if len(trends) >= 2:
            recent_avg = sum(row["request_count"] for row in trends[-3:]) / min(3, len(trends))
            earlier_avg = sum(row["request_count"] for row in trends[:3]) / min(3, len(trends))
            growth_rate = ((recent_avg - earlier_avg) / earlier_avg * 100) if earlier_avg > 0 else 0
        else:
            growth_rate = 0
        
        return {
            "period": period,
            "granularity": granularity,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "growth_rate_percent": round(growth_rate, 2),
            "data": [
                {
                    "date": row["date"].isoformat() if hasattr(row["date"], 'isoformat') else str(row["date"]),
                    "request_count": row["request_count"],
                    "unique_wallets": row["unique_wallets"]
                }
                for row in trends
            ]
        }
    
    async def get_wallet_analytics(
        self, 
        wallet_address: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Get wallet-specific analytics"""
        
        if wallet_address:
            # Analytics for specific wallet
            wallet_query = """
                SELECT 
                    COUNT(*) as total_requests,
                    MIN(request_timestamp) as first_request,
                    MAX(request_timestamp) as last_request,
                    COUNT(DISTINCT endpoint) as endpoints_used,
                    AVG(response_time_ms) as avg_response_time
                FROM api_usage 
                WHERE wallet_address = :wallet_address
            """
            wallet_stats = await database.fetch_one(
                wallet_query,
                {"wallet_address": wallet_address.lower()}
            )
            
            # Get endpoint breakdown for this wallet
            endpoint_breakdown_query = """
                SELECT endpoint, COUNT(*) as request_count
                FROM api_usage 
                WHERE wallet_address = :wallet_address
                GROUP BY endpoint
                ORDER BY request_count DESC
            """
            endpoint_breakdown = await database.fetch_all(
                endpoint_breakdown_query,
                {"wallet_address": wallet_address.lower()}
            )
            
            # Get recent activity
            recent_activity_query = """
                SELECT endpoint, request_timestamp, status_code, response_time_ms
                FROM api_usage 
                WHERE wallet_address = :wallet_address
                ORDER BY request_timestamp DESC
                LIMIT 20
            """
            recent_activity = await database.fetch_all(
                recent_activity_query,
                {"wallet_address": wallet_address.lower()}
            )
            
            return {
                "wallet_address": wallet_address,
                "statistics": {
                    "total_requests": wallet_stats["total_requests"] if wallet_stats else 0,
                    "first_request": wallet_stats["first_request"].isoformat() if wallet_stats and wallet_stats["first_request"] else None,
                    "last_request": wallet_stats["last_request"].isoformat() if wallet_stats and wallet_stats["last_request"] else None,
                    "endpoints_used": wallet_stats["endpoints_used"] if wallet_stats else 0,
                    "avg_response_time_ms": float(wallet_stats["avg_response_time"]) if wallet_stats and wallet_stats["avg_response_time"] else None
                },
                "endpoint_breakdown": [
                    {
                        "endpoint": row["endpoint"],
                        "request_count": row["request_count"]
                    }
                    for row in endpoint_breakdown
                ],
                "recent_activity": [
                    {
                        "endpoint": row["endpoint"],
                        "timestamp": row["request_timestamp"].isoformat(),
                        "status_code": row["status_code"],
                        "response_time_ms": row["response_time_ms"]
                    }
                    for row in recent_activity
                ]
            }
        else:
            # Top wallets analytics
            top_wallets_query = """
                SELECT 
                    wallet_address,
                    COUNT(*) as total_requests,
                    MIN(request_timestamp) as first_request,
                    MAX(request_timestamp) as last_request,
                    COUNT(DISTINCT endpoint) as endpoints_used
                FROM api_usage 
                GROUP BY wallet_address
                ORDER BY total_requests DESC
                LIMIT :limit
            """
            top_wallets = await database.fetch_all(
                top_wallets_query,
                {"limit": limit}
            )
            
            return {
                "top_wallets": [
                    {
                        "wallet_address": row["wallet_address"],
                        "total_requests": row["total_requests"],
                        "first_request": row["first_request"].isoformat(),
                        "last_request": row["last_request"].isoformat(),
                        "endpoints_used": row["endpoints_used"]
                    }
                    for row in top_wallets
                ]
            }
    
    async def get_endpoint_analytics(self) -> Dict[str, Any]:
        """Get endpoint performance analytics"""
        
        # Endpoint usage statistics
        endpoint_stats_query = """
            SELECT 
                endpoint,
                COUNT(*) as total_requests,
                COUNT(DISTINCT wallet_address) as unique_users,
                AVG(response_time_ms) as avg_response_time,
                MIN(response_time_ms) as min_response_time,
                MAX(response_time_ms) as max_response_time,
                COUNT(CASE WHEN status_code >= 400 THEN 1 END) * 100.0 / COUNT(*) as error_rate
            FROM api_usage 
            WHERE response_time_ms IS NOT NULL OR status_code IS NOT NULL
            GROUP BY endpoint
            ORDER BY total_requests DESC
        """
        endpoint_stats = await database.fetch_all(endpoint_stats_query)
        
        # Recent endpoint performance trends (last 24 hours)
        performance_trends_query = """
            SELECT 
                endpoint,
                DATE_TRUNC('hour', request_timestamp) as hour,
                COUNT(*) as request_count,
                AVG(response_time_ms) as avg_response_time
            FROM api_usage 
            WHERE request_timestamp >= NOW() - INTERVAL '24 hours'
            AND response_time_ms IS NOT NULL
            GROUP BY endpoint, DATE_TRUNC('hour', request_timestamp)
            ORDER BY endpoint, hour
        """
        performance_trends = await database.fetch_all(performance_trends_query)
        
        return {
            "endpoint_statistics": [
                {
                    "endpoint": row["endpoint"],
                    "total_requests": row["total_requests"],
                    "unique_users": row["unique_users"],
                    "performance": {
                        "avg_response_time_ms": float(row["avg_response_time"]) if row["avg_response_time"] else None,
                        "min_response_time_ms": row["min_response_time"],
                        "max_response_time_ms": row["max_response_time"]
                    },
                    "error_rate_percent": float(row["error_rate"]) if row["error_rate"] else None
                }
                for row in endpoint_stats
            ],
            "performance_trends": [
                {
                    "endpoint": row["endpoint"],
                    "hour": row["hour"].isoformat(),
                    "request_count": row["request_count"],
                    "avg_response_time_ms": float(row["avg_response_time"]) if row["avg_response_time"] else None
                }
                for row in performance_trends
            ]
        }

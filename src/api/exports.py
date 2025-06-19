from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from datetime import datetime

from src.models.schemas import CSVExportRequest, TransactionFilter, TransactionType
from src.services.csv_export import CSVExportService
from src.api.auth import verify_api_key

router = APIRouter(prefix="/exports", tags=["exports"])

@router.get("/csv/{wallet_address}")
async def export_transactions_csv_get(
    wallet_address: str,
    start_date: datetime = None,
    end_date: datetime = None,
    transaction_types: Optional[List[TransactionType]] = Query(None, description="Filter by transaction types (can specify multiple)"),
    api_key: str = Depends(verify_api_key)
) -> StreamingResponse:
    """
    Export wallet transactions to CSV via GET request
    Alternative endpoint for CSV export with query parameters
    """
    
    filters = TransactionFilter(
        start_date=start_date,
        end_date=end_date,
        transaction_types=transaction_types
    )
    
    export_request = CSVExportRequest(
        wallet_address=wallet_address,
        filters=filters
    )
    
    service = CSVExportService()
    
    try:
        return await service.export_transactions_csv(
            wallet_address=export_request.wallet_address,
            filters=export_request.filters
        )
    
    except HTTPException:
        # Re-raise HTTPExceptions (like large dataset errors)
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate CSV export: {str(e)}"
        )
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime

from src.models.schemas import CSVExportRequest, TransactionFilter
from src.services.csv_export import CSVExportService
from src.api.auth import verify_api_key

router = APIRouter(prefix="/exports", tags=["exports"])

@router.post("/csv")
async def export_transactions_csv(
    export_request: CSVExportRequest,
    api_key: str = Depends(verify_api_key)
) -> StreamingResponse:
    """
    Export wallet transactions to CSV file
    
    CSV includes the following fields:
    - Transaction Hash
    - Date & Time (transaction confirmation timestamp)
    - From Address
    - To Address  
    - Transaction Type (ETH, ERC-20, ERC-721, ERC-1155, Internal)
    - Asset Contract Address (for tokens/NFTs)
    - Asset Symbol/Name (ETH, USDC, NFT collection name)
    - Token ID (for NFTs)
    - Value/Amount (quantity transferred)
    - Gas Fee (ETH)
    """
    
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

@router.get("/csv/{wallet_address}")
async def export_transactions_csv_get(
    wallet_address: str,
    start_date: datetime = None,
    end_date: datetime = None,
    api_key: str = Depends(verify_api_key)
) -> StreamingResponse:
    """
    Export wallet transactions to CSV via GET request
    Alternative endpoint for CSV export with query parameters
    """
    
    filters = TransactionFilter(
        start_date=start_date,
        end_date=end_date
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
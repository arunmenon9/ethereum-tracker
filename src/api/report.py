# src/api/reports.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from typing import Optional

from src.services.report import ReportService
from src.api.auth import verify_api_key
from src.models.schemas import ReportRequest, ReportStatusResponse, ReportGenerationResponse
from src.utils.validators import AddressValidator

router = APIRouter(prefix="/reports", tags=["reports"])

@router.post("/generate", response_model=ReportGenerationResponse)
async def generate_report(
    report_request: ReportRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Generate a comprehensive transaction report for addresses with large datasets
    
    This endpoint is designed for addresses that have too many transactions 
    to display immediately. It will:
    
    1. Start a background job to collect all transactions using block range segmentation
    2. Process and filter the data according to the provided filters
    3. Generate a CSV file with all transactions
    4. Return a report ID for checking status
    
    The process typically takes 2-10 minutes depending on the number of transactions.
    """
    
    service = ReportService()
    
    try:
        result = await service.generate_report(
            wallet_address=report_request.wallet_address,
            filters=report_request.filters
        )
        return ReportGenerationResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start report generation: {str(e)}"
        )

@router.get("/status/{wallet_address}", response_model=ReportStatusResponse)
async def get_report_status(
    wallet_address: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Get the status of a report generation job
    
    Returns:
    - pending: Report is queued for processing
    - in_progress: Report is being generated (includes progress percentage)
    - completed: Report is ready for download
    - failed: Report generation failed (includes error message)
    """
    
    service = ReportService()
    
    try:
        return await service.get_report_status(wallet_address)
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

@router.get("/download/{wallet_address}")
async def download_report(
    wallet_address: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Download the completed transaction report as CSV
    
    This endpoint returns the CSV file containing all transactions
    for the specified wallet address. The report must be completed
    before it can be downloaded.
    """
    
    service = ReportService()
    
    try:
        file_path = await service.download_report(wallet_address)
        
        # Validate address for filename
        validated_address = AddressValidator.validate_ethereum_address(wallet_address)
        
        return FileResponse(
            path=file_path,
            media_type='text/csv',
            filename=f"ethereum_transactions_{validated_address[:8]}.csv"
        )
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

@router.delete("/clear/{wallet_address}")
async def clear_report(
    wallet_address: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Clear/delete report data for a wallet address
    
    This will remove the report job record and delete the CSV file
    to free up storage space.
    """
    
    service = ReportService()
    
    try:
        await service.clear_report(wallet_address)
        return {
            "message": "Report cleared successfully",
            "wallet_address": wallet_address
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear report: {str(e)}"
        )
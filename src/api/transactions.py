from fastapi import APIRouter, Depends, Query, HTTPException, Request
from typing import Optional, List
from datetime import datetime

from src.models.schemas import TransactionResponse, TransactionFilter, TransactionListResponse
from src.services.transaction import TransactionService
from src.api.auth import verify_api_key
from src.utils.validators import AddressValidator

router = APIRouter(prefix="/transactions", tags=["transactions"])

@router.get("/{wallet_address}", response_model=TransactionListResponse)
async def get_transactions(
    wallet_address: str,
    start_date: Optional[datetime] = Query(None, description="Start date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"),
    end_date: Optional[datetime] = Query(None, description="End date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"),
    transaction_types: Optional[List[str]] = Query(None, description="Filter by transaction types"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    api_key: str = Depends(verify_api_key)
):
    """
    Get Ethereum transactions for a wallet address
    
    Supports filtering by:
    - Date range (start_date, end_date)  
    - Transaction types (ETH, ERC-20, ERC-721, ERC-1155, Internal)
    - Pagination
    
    Returns all transaction categories:
    - External/Normal transfers (direct ETH transfers)
    - Internal transfers (smart contract internal transfers)
    - Token transfers (ERC-20, ERC-721, ERC-1155)
    """
    
    # Validate wallet address
    try:
        validated_address = AddressValidator.validate_ethereum_address(wallet_address)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Create filters
    filters = TransactionFilter(
        start_date=start_date,
        end_date=end_date,
        transaction_types=transaction_types
    )
    
    # Get transactions
    service = TransactionService()
    result = await service.get_transactions(
        wallet_address=validated_address,
        filters=filters,
        page=page,
        page_size=page_size
    )
    
    return TransactionListResponse(**result)

@router.get("/{wallet_address}/summary")
async def get_transaction_summary(
    wallet_address: str,
    api_key: str = Depends(verify_api_key)
):
    """Get transaction summary statistics for a wallet"""
    
    validated_address = AddressValidator.validate_ethereum_address(wallet_address)
    
    service = TransactionService()
    result = await service.get_transactions(
        wallet_address=validated_address,
        page=1,
        page_size=10000  # Get all for summary
    )
    
    transactions = result['transactions']
    
    # Calculate summary statistics
    total_transactions = len(transactions)
    transaction_type_counts = {}
    total_gas_fees = 0
    
    for tx in transactions:
        # Count by type
        tx_type = tx.transaction_type
        transaction_type_counts[tx_type] = transaction_type_counts.get(tx_type, 0) + 1
        
        # Sum gas fees
        total_gas_fees += float(tx.gas_fee)
    
    return {
        "wallet_address": validated_address,
        "total_transactions": total_transactions,
        "transaction_type_breakdown": transaction_type_counts,
        "total_gas_fees_eth": round(total_gas_fees, 6),
        "date_range": {
            "earliest": min(tx.timestamp for tx in transactions) if transactions else None,
            "latest": max(tx.timestamp for tx in transactions) if transactions else None
        }
    }
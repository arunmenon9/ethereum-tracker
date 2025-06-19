import csv
from fastapi import HTTPException
import io
from typing import List, AsyncIterator
from fastapi.responses import StreamingResponse
from decimal import Decimal
from datetime import datetime 
from src.models.schemas import TransactionResponse, TransactionFilter
from src.services.transaction import TransactionService

class CSVExportService:
    def __init__(self):
        self.transaction_service = TransactionService()
    
    
    async def export_transactions_csv(
    self, 
    wallet_address: str, 
    filters: TransactionFilter
    ) -> StreamingResponse:
        """Export transactions as CSV with streaming response"""
        
        # Get all transactions
        result = await self.transaction_service.get_transactions(
            wallet_address=wallet_address,
            filters=filters,
            page=1,
            page_size=500000  # Large page size for export
        )
        
        # Check if this is a large dataset error
        if result.get('error') == 'large_dataset':
            raise HTTPException(
                status_code=422,  # Unprocessable Entity
                detail={
                    "error": "large_dataset",
                    "message": result.get('message', 'Address has too many transactions for direct CSV export'),
                    "suggestion": "Use the reports endpoint for large datasets",
                    "report_endpoint": "/api/v1/reports/generate",
                    "wallet_address": wallet_address
                }
            )
        
        async def generate_csv_data() -> AsyncIterator[str]:
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write CSV header
            headers = [
                'Transaction Hash',
                'Date & Time',
                'From Address',
                'To Address', 
                'Transaction Type',
                'Asset Contract Address',
                'Asset Symbol/Name',
                'Token ID',
                'Value/Amount',
                'Gas Fee (ETH)'
            ]
            writer.writerow(headers)
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)
            
            # Write transaction data - now we know 'transactions' key exists
            for tx in result['transactions']:
                row = [
                    tx.tx_hash,
                    tx.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC'),
                    tx.from_address,
                    tx.to_address or '',
                    tx.transaction_type,
                    tx.token_address or '',
                    tx.token_symbol or tx.token_name or 'ETH',
                    tx.token_id or '',
                    tx.value,
                    tx.gas_fee
                ]
                writer.writerow(row)
                
                # Yield data in chunks
                if output.tell() > 8192:  # 8KB chunks
                    yield output.getvalue()
                    output.seek(0)
                    output.truncate(0)
            
            # Yield remaining data
            if output.tell() > 0:
                yield output.getvalue()
        
        filename = f"ethereum_transactions_{wallet_address[:8]}_{int(datetime.now().timestamp())}.csv"
        
        return StreamingResponse(
            generate_csv_data(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
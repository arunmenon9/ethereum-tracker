# src/services/report.py
import asyncio
import csv
import os
import traceback
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import aiofiles
import logging

from src.services.etherscan import EtherscanClient
from src.models.schemas import TransactionFilter, ReportStatus, ReportStatusResponse
from src.database import database
from src.config import get_settings
from src.utils.validators import AddressValidator

from .transaction import TransactionService

logger = logging.getLogger(__name__)
settings = get_settings()

class ReportService:
    def __init__(self):
        self.reports_dir = Path("/tmp/reports")
        self.reports_dir.mkdir(exist_ok=True)
    
    async def generate_report(self, wallet_address: str, filters: TransactionFilter) -> Dict[str, Any]:
        """Generate a comprehensive transaction report for large datasets"""
        
        validated_address = AddressValidator.validate_ethereum_address(wallet_address)
        
        # Check if report already exists and is recent
        existing_report = await self._get_recent_report(validated_address)
        if existing_report:
            return {
                "message": "Report already exists or is in progress",
                "wallet_address": validated_address,
                "status": existing_report["status"],
                "report_id": existing_report["report_id"],
                "status_endpoint": f"/api/v1/reports/status/{validated_address}"
            }
        
        # Create new report job
        report_id = str(uuid.uuid4())
        
        await database.execute("""
            INSERT INTO report_jobs 
            (report_id, wallet_address, status, filters)
            VALUES (:report_id, :wallet_address, :status, :filters)
        """, {
            "report_id": report_id,
            "wallet_address": validated_address,
            "status": ReportStatus.PENDING.value,
            "filters": filters.model_dump_json() if filters else "{}"
        })
        
        # Start background task
        asyncio.create_task(self._process_report_background(report_id, validated_address, filters))
        
        return {
            "message": "Report generation started",
            "wallet_address": validated_address,
            "status": ReportStatus.PENDING.value,
            "report_id": report_id,
            "status_endpoint": f"/api/v1/reports/status/{validated_address}",
            "estimated_time_minutes": 5  # Rough estimate
        }
    
    async def get_report_status(self, wallet_address: str) -> ReportStatusResponse:
        """Get the status of a report generation"""
        
        validated_address = AddressValidator.validate_ethereum_address(wallet_address)
        
        report = await database.fetch_one("""
            SELECT * FROM report_jobs 
            WHERE wallet_address = :wallet_address 
            ORDER BY created_at DESC 
            LIMIT 1
        """, {"wallet_address": validated_address})
        
        if not report:
            raise Exception("No report found for this address")
        
        return ReportStatusResponse(
            wallet_address=validated_address,
            status=ReportStatus(report["status"]),
            created_at=report["created_at"],
            updated_at=report["updated_at"],
            progress_percentage=report["progress_percentage"],
            estimated_completion=self._calculate_estimated_completion(report),
            error_message=report["error_message"],
            file_size_mb=float(report["file_size_mb"]) if report["file_size_mb"] else None,
            total_transactions=report["total_transactions"]
        )
    
    async def download_report(self, wallet_address: str) -> str:
        """Get the file path for downloading the completed report"""
        
        validated_address = AddressValidator.validate_ethereum_address(wallet_address)
        
        report = await database.fetch_one("""
            SELECT file_path FROM report_jobs 
            WHERE wallet_address = :wallet_address 
            AND status = :status
            ORDER BY created_at DESC 
            LIMIT 1
        """, {
            "wallet_address": validated_address,
            "status": ReportStatus.COMPLETED.value
        })
        
        if not report or not report["file_path"]:
            raise Exception("No completed report found for this address")
        
        file_path = Path(report["file_path"])
        if not file_path.exists():
            raise Exception("Report file not found")
        
        return str(file_path)
    
    async def _get_recent_report(self, wallet_address: str) -> Optional[Dict]:
        """Check if there's a recent report for this address"""
        
        # Check for reports from last 24 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        return await database.fetch_one("""
            SELECT report_id, status FROM report_jobs 
            WHERE wallet_address = :wallet_address 
            AND created_at > :cutoff_time
            AND status IN ('pending', 'in_progress', 'completed')
            ORDER BY created_at DESC 
            LIMIT 1
        """, {
            "wallet_address": wallet_address,
            "cutoff_time": cutoff_time
        })
    
    async def _process_report_background(self, report_id: str, wallet_address: str, filters: TransactionFilter):
        """Background task to process the report"""
        
        try:
            # Update status to in_progress
            await database.execute("""
                UPDATE report_jobs 
                SET status = :status, started_at = :started_at, updated_at = :updated_at
                WHERE report_id = :report_id
            """, {
                "status": ReportStatus.IN_PROGRESS.value,
                "started_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "report_id": report_id
            })
            
            # Generate the report using block range segmentation
            transactions = await self._collect_all_transactions_with_progress(
                wallet_address, filters, report_id
            )
            
            # Save to CSV
            file_path = await self._save_to_csv(wallet_address, transactions, report_id)
            
            # Update completion status
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            
            await database.execute("""
                UPDATE report_jobs 
                SET status = :status, completed_at = :completed_at, updated_at = :updated_at,
                    file_path = :file_path, file_size_mb = :file_size_mb, 
                    total_transactions = :total_transactions, progress_percentage = 100
                WHERE report_id = :report_id
            """, {
                "status": ReportStatus.COMPLETED.value,
                "completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "file_path": str(file_path),
                "file_size_mb": file_size_mb,
                "total_transactions": len(transactions),
                "report_id": report_id
            })
            
            logger.info(f"Report {report_id} completed successfully with {len(transactions)} transactions")
            
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Report {report_id} failed: {str(e)}")
            
            await database.execute("""
                UPDATE report_jobs 
                SET status = :status, updated_at = :updated_at, error_message = :error_message
                WHERE report_id = :report_id
            """, {
                "status": ReportStatus.FAILED.value,
                "updated_at": datetime.utcnow(),
                "error_message": str(e),
                "report_id": report_id
            })
    
    async def _collect_all_transactions_with_progress(
        self, wallet_address: str, filters: TransactionFilter, report_id: str
    ) -> list:
        """Collect all transactions using block range segmentation with progress updates"""
        
        async with EtherscanClient() as client:
            # Get current block number
            current_block = await client.get_current_block_number()
            
            all_transactions = []
            block_range_size = 1500000  # Smaller ranges for more frequent progress updates
            total_ranges = (current_block // block_range_size) + 1
            processed_ranges = 0
            
            start_block = 0
            while start_block < current_block:
                end_block = min(start_block + block_range_size, current_block)
                
                # Get transactions for this block range
                range_transactions = await client.get_all_transactions_block_range(
                    wallet_address, start_block, end_block
                )
                
                # Process and add transactions
                for tx_type, transactions in range_transactions.items():
                    for tx in transactions:
                        processed_tx = TransactionService.process_transaction_for_report(tx, tx_type)
                        if TransactionService.transaction_matches_filters(processed_tx, filters):
                            all_transactions.append(processed_tx)
                
                # Update progress
                processed_ranges += 1
                progress = int((processed_ranges / total_ranges) * 100)
                
                await database.execute("""
                    UPDATE report_jobs 
                    SET progress_percentage = :progress, updated_at = :updated_at
                    WHERE report_id = :report_id
                """, {
                    "progress": progress,
                    "updated_at": datetime.utcnow(),
                    "report_id": report_id
                })
                
                start_block = end_block + 1
                
                # Rate limiting
                await asyncio.sleep(0.2)
            
            return all_transactions
    
    async def _save_to_csv(self, wallet_address: str, transactions: list, report_id: str) -> Path:
        """Save transactions to CSV file"""
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"ethereum_transactions_{wallet_address[:8]}_{timestamp}.csv"
        file_path = self.reports_dir / filename
        
        async with aiofiles.open(file_path, mode='w', newline='', encoding='utf-8') as file:
            # Write CSV header
            headers = [
                'Transaction Hash', 'Date & Time', 'From Address', 'To Address',
                'Transaction Type', 'Asset Contract Address', 'Asset Symbol/Name',
                'Token ID', 'Value/Amount', 'Gas Fee (ETH)'
            ]
            
            await file.write(','.join(headers) + '\n')
            
            # Write transaction data
            print(f"THE TXS ARE : {transactions}")
            for tx in transactions:
                row = [
                    tx.get('tx_hash', ''),
                    tx.get('timestamp', ''),
                    tx.get('from_address', ''),
                    tx.get('to_address', ''),
                    tx.get('transaction_type', ''),
                    tx.get('token_address', ''),
                    tx.get('token_symbol', ''),
                    tx.get('token_id', ''),
                    tx.get('value', ''),
                    tx.get('gas_fee', '')
                ]
                
                # Escape commas and quotes in CSV
                escaped_row = []
                for field in row:
                    field_str = str(field) if field else ''
                    if ',' in field_str or '"' in field_str:
                        field_str = f'"{field_str.replace(""", """"")}"'
                    escaped_row.append(field_str)
                
                await file.write(','.join(escaped_row) + '\n')
        
        return file_path
    
    def _calculate_estimated_completion(self, report: Dict) -> Optional[datetime]:
        """Calculate estimated completion time based on progress"""
        if report["status"] == ReportStatus.COMPLETED.value:
            return report["completed_at"]
        
        if report["status"] == ReportStatus.IN_PROGRESS.value and report["progress_percentage"]:
            # Simple estimation based on progress
            elapsed = datetime.utcnow() - report["started_at"]
            if report["progress_percentage"] > 0:
                total_estimated = elapsed / (report["progress_percentage"] / 100)
                return report["started_at"] + total_estimated
        
        return None
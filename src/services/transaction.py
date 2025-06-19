import logging
import traceback
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

from src.services.etherscan import EtherscanClient, PaginationLimitExceeded
from src.models.schemas import TransactionResponse, TransactionFilter, TransactionType
from src.database import database
from src.utils.validators import AddressValidator

logger = logging.getLogger(__name__)

class TransactionService:
    def __init__(self):
        self.etherscan_client = None


    @staticmethod
    def process_transaction_for_report(tx: Dict, tx_type: str) -> Dict[str, Any]:
        """Process transaction for report format (returns dict for CSV generation)"""
        try:
            # Common fields
            if isinstance(tx, str):
                return None
            base_data = {
                'tx_hash': tx.get('hash', ''),
                'block_number': int(tx.get('blockNumber', 0)),
                'timestamp': datetime.fromtimestamp(int(tx.get('timeStamp', 0))).strftime('%Y-%m-%d %H:%M:%S UTC'),
                'from_address': tx.get('from', '').lower(),
                'to_address': tx.get('to', '').lower() if tx.get('to') else '',
                'token_address': '',
                'token_symbol': '',
                'token_name': '',
                'token_id': '',
                'value': '0',
                'gas_fee': '0'
            }
            
            if tx_type == 'normal':
                base_data.update({
                    'transaction_type': 'ETH',
                    'token_symbol': 'ETH',
                    'value': str(Decimal(tx.get('value', 0)) / Decimal(10**18)),
                    'gas_fee': str(Decimal(tx.get('gasUsed', 0)) * Decimal(tx.get('gasPrice', 0)) / Decimal(10**18))
                })
            
            elif tx_type == 'internal':
                base_data.update({
                    'transaction_type': 'Internal',
                    'token_symbol': 'ETH',
                    'value': str(Decimal(tx.get('value', 0)) / Decimal(10**18)),
                    'gas_fee': '0'  # Internal transactions don't have direct gas fees
                })
            
            elif tx_type == 'token':
                decimals = int(tx.get('tokenDecimal', 18))
                token_value = Decimal(tx.get('value', 0)) / Decimal(10 ** decimals)
                
                base_data.update({
                    'transaction_type': 'ERC-20',
                    'token_address': tx.get('contractAddress', '').lower(),
                    'token_symbol': tx.get('tokenSymbol', ''),
                    'token_name': tx.get('tokenName', ''),
                    'value': str(token_value),
                    'gas_fee': str(Decimal(tx.get('gasUsed', 0)) * Decimal(tx.get('gasPrice', 0)) / Decimal(10**18))
                })
            
            elif tx_type == 'nft':
                base_data.update({
                    'transaction_type': 'ERC-721',
                    'token_address': tx.get('contractAddress', '').lower(),
                    'token_symbol': tx.get('tokenSymbol', ''),
                    'token_name': tx.get('tokenName', ''),
                    'token_id': tx.get('tokenID', ''),
                    'value': '1',
                    'gas_fee': str(Decimal(tx.get('gasUsed', 0)) * Decimal(tx.get('gasPrice', 0)) / Decimal(10**18))
                })
            
            return base_data
            
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Error processing transaction for report: {e}, tx: {tx}")
            # Return minimal data to avoid breaking the report
            return {
                'tx_hash': tx.get('hash', 'unknown'),
                'block_number': tx.get('blockNumber', 0),
                'timestamp': datetime.fromtimestamp(int(tx.get('timeStamp', 0)) if tx.get('timeStamp') else 0).strftime('%Y-%m-%d %H:%M:%S UTC'),
                'from_address': tx.get('from', '').lower(),
                'to_address': tx.get('to', '').lower() if tx.get('to') else '',
                'transaction_type': tx_type.title(),
                'token_address': '',
                'token_symbol': '',
                'token_name': '',
                'token_id': '',
                'value': '0',
                'gas_fee': '0'
            }
    
    def _apply_filters(self, transactions: List[TransactionResponse], filters: TransactionFilter) -> List[TransactionResponse]:
        """Apply filters to transaction list"""
        filtered_transactions = transactions
        
        if filters.start_date:
            filtered_transactions = [tx for tx in filtered_transactions if tx.timestamp >= filters.start_date]
        
        if filters.end_date:
            filtered_transactions = [tx for tx in filtered_transactions if tx.timestamp <= filters.end_date]
        
        if filters.transaction_types:
            filtered_transactions = [tx for tx in filtered_transactions if tx.transaction_type in filters.transaction_types]
        
        if filters.min_value:
            filtered_transactions = [tx for tx in filtered_transactions if Decimal(tx.value) >= filters.min_value]
        
        if filters.max_value:
            filtered_transactions = [tx for tx in filtered_transactions if Decimal(tx.value) <= filters.max_value]
        
        return filtered_transactions
    
    @staticmethod
    def transaction_matches_filters(tx: Dict[str, Any], filters: Optional[TransactionFilter]) -> bool:
        """Check if transaction matches the provided filters"""
        if not filters:
            return True
        
        try:
            # Parse timestamp from string
            tx_timestamp = datetime.strptime(tx['timestamp'], '%Y-%m-%d %H:%M:%S UTC')
            
            if filters.start_date and tx_timestamp < filters.start_date:
                return False
            
            if filters.end_date and tx_timestamp > filters.end_date:
                return False
            
            if filters.transaction_types and tx['transaction_type'] not in [t.value for t in filters.transaction_types]:
                return False
            
            if filters.min_value:
                try:
                    tx_value = Decimal(tx['value'])
                    if tx_value < filters.min_value:
                        return False
                except (ValueError, TypeError):
                    pass
            
            if filters.max_value:
                try:
                    tx_value = Decimal(tx['value'])
                    if tx_value > filters.max_value:
                        return False
                except (ValueError, TypeError):
                    pass
            return True
            
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Error applying filters to transaction: {e}")
            return True  # Include transaction if filter check fails
    
    async def get_transactions(
        self, 
        wallet_address: str, 
        filters: Optional[TransactionFilter] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """Get transactions for a wallet address with filtering"""
        
        # Validate address
        validated_address = AddressValidator.validate_ethereum_address(wallet_address)
        
        try:
            async with EtherscanClient() as client:
                # Get all transaction types
                all_transactions = await client.get_all_transactions(validated_address)
                
                # Process and normalize transactions
                processed_transactions = []
                
                # Process normal transactions
                for tx in all_transactions.get('normal', []):
                    if tx:  # Check if transaction data is valid 
                        processed_tx = self._process_normal_transaction(tx)
                        processed_transactions.append(processed_tx)
                
                # Process internal transactions
                for tx in all_transactions.get('internal', []):
                    if tx:
                        processed_tx = self._process_internal_transaction(tx)
                        processed_transactions.append(processed_tx)
                
                # Process token transfers
                for tx in all_transactions.get('token', []):
                    if tx:
                        processed_tx = self._process_token_transaction(tx)
                        processed_transactions.append(processed_tx)
                
                # Process NFT transfers
                for tx in all_transactions.get('nft', []):
                    if tx:
                        processed_tx = self._process_nft_transaction(tx)
                        processed_transactions.append(processed_tx)
        
        except PaginationLimitExceeded:
            # Handle large datasets
            logger.warning(f"Pagination limit exceeded for address {validated_address}")
            return {
                "error": "large_dataset",
                "message": "This address has a large number of transactions that cannot be displayed immediately.",
                "suggestion": "Please use the /api/v1/reports/generate endpoint to request a full report.",
                "wallet_address": validated_address,
                "report_endpoint": f"/api/v1/reports/generate",
                "status_endpoint": f"/api/v1/reports/status/{validated_address}",
                "estimated_time": "2-10 minutes depending on transaction count"
            }
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error fetching transactions for {validated_address}: {str(e)}")
            raise Exception(f"Failed to fetch transactions: {str(e)}")
        
        # Apply filters
        if filters:
            processed_transactions = self._apply_filters(processed_transactions, filters)
        
        # Sort by timestamp (newest first)
        processed_transactions.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Pagination
        total_count = len(processed_transactions)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_transactions = processed_transactions[start_idx:end_idx]
        
        # Store usage stats
        await self._log_api_usage(validated_address, "get_transactions")
        
        return {
            "transactions": paginated_transactions,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "has_more": end_idx < total_count
        }
    
    async def get_transactions_for_report(
        self, 
        wallet_address: str, 
        filters: Optional[TransactionFilter] = None,
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """Get all transactions for report generation using block range segmentation"""
        
        validated_address = AddressValidator.validate_ethereum_address(wallet_address)
        
        async with EtherscanClient() as client:
            # Get current block number
            current_block = await client.get_current_block_number()
            if current_block == 0:
                logger.warning("Could not get current block number, using default")
                current_block = 20000000  # Fallback to approximate current block
            
            all_transactions = []
            block_range_size = 100000  # Smaller ranges for more frequent progress updates
            total_ranges = (current_block // block_range_size) + 1
            processed_ranges = 0
            
            logger.info(f"Starting report generation for {validated_address}, processing {total_ranges} block ranges")
            
            start_block = 0
            while start_block < current_block:
                end_block = min(start_block + block_range_size, current_block)
                
                try:
                    # Get transactions for this block range
                    range_transactions = await client.get_all_transactions_block_range(
                        validated_address, start_block, end_block
                    )
                    
                    # Process each transaction type
                    for tx_type, transactions in range_transactions.items():
                        for tx in transactions:
                            if tx:  # Ensure transaction data is valid
                                processed_tx = self.process_transaction_for_report(tx, tx_type)
                                if processed_tx:
                                    if self.transaction_matches_filters(processed_tx, filters):
                                        all_transactions.append(processed_tx)
                    
                    processed_ranges += 1
                    progress = int((processed_ranges / total_ranges) * 100)
                    
                    # Call progress callback if provided
                    if progress_callback:
                        await progress_callback(progress)
                    
                    logger.debug(f"Processed block range {start_block}-{end_block}, progress: {progress}%")
                    
                except Exception as e:
                    logger.warning(f"Error processing block range {start_block}-{end_block}: {str(e)}")
                    # Continue with next range instead of failing completely
                
                start_block = end_block + 1
                
                # Rate limiting between ranges
                await asyncio.sleep(0.1)
            
            logger.info(f"Report generation completed for {validated_address}, found {len(all_transactions)} transactions")
            return all_transactions
    
    def _process_normal_transaction(self, tx: Dict) -> TransactionResponse:
        """Process normal ETH transaction"""
        try:
            return TransactionResponse(
                tx_hash=tx.get('hash', ''),
                block_number=int(tx.get('blockNumber', 0)),
                timestamp=datetime.fromtimestamp(int(tx.get('timeStamp', 0))),
                from_address=tx.get('from', '').lower(),
                to_address=tx.get('to', '').lower() if tx.get('to') else None,
                transaction_type=TransactionType.ETH,
                value=str(Decimal(tx.get('value', 0)) / Decimal(10**18)),  # Convert Wei to ETH
                gas_fee=str(Decimal(tx.get('gasUsed', 0)) * Decimal(tx.get('gasPrice', 0)) / Decimal(10**18))
            )
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Error processing normal transaction: {e}, tx: {tx}")
            # Return a default transaction with available data
            return TransactionResponse(
                tx_hash=tx.get('hash', 'unknown'),
                block_number=int(tx.get('blockNumber', 0)),
                timestamp=datetime.fromtimestamp(int(tx.get('timeStamp', 0)) if tx.get('timeStamp') else 0),
                from_address=tx.get('from', '').lower(),
                to_address=tx.get('to', '').lower() if tx.get('to') else None,
                transaction_type=TransactionType.ETH,
                value="0",
                gas_fee="0"
            )
    
    def _process_internal_transaction(self, tx: Dict) -> TransactionResponse:
        """Process internal transaction"""
        try:
            return TransactionResponse(
                tx_hash=tx.get('hash', ''),
                block_number=int(tx.get('blockNumber', 0)),
                timestamp=datetime.fromtimestamp(int(tx.get('timeStamp', 0))),
                from_address=tx.get('from', '').lower(),
                to_address=tx.get('to', '').lower() if tx.get('to') else None,
                transaction_type=TransactionType.INTERNAL,
                value=str(Decimal(tx.get('value', 0)) / Decimal(10**18)),
                gas_fee="0"  # Internal transactions don't have direct gas fees
            )
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Error processing internal transaction: {e}, tx: {tx}")
            return TransactionResponse(
                tx_hash=tx.get('hash', 'unknown'),
                block_number=int(tx.get('blockNumber', 0)),
                timestamp=datetime.fromtimestamp(int(tx.get('timeStamp', 0)) if tx.get('timeStamp') else 0),
                from_address=tx.get('from', '').lower(),
                to_address=tx.get('to', '').lower() if tx.get('to') else None,
                transaction_type=TransactionType.INTERNAL,
                value="0",
                gas_fee="0"
            )
    
    def _process_token_transaction(self, tx: Dict) -> TransactionResponse:
        """Process ERC-20 token transaction"""
        try:
            decimals = int(tx.get('tokenDecimal', 18))
            token_value = Decimal(tx.get('value', 0)) / Decimal(10 ** decimals)
            
            return TransactionResponse(
                tx_hash=tx.get('hash', ''),
                block_number=int(tx.get('blockNumber', 0)),
                timestamp=datetime.fromtimestamp(int(tx.get('timeStamp', 0))),
                from_address=tx.get('from', '').lower(),
                to_address=tx.get('to', '').lower(),
                transaction_type=TransactionType.ERC20,
                token_address=tx.get('contractAddress', '').lower(),
                token_symbol=tx.get('tokenSymbol', ''),
                token_name=tx.get('tokenName', ''),
                value=str(token_value),
                gas_fee=str(Decimal(tx.get('gasUsed', 0)) * Decimal(tx.get('gasPrice', 0)) / Decimal(10**18))
            )
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Error processing token transaction: {e}, tx: {tx}")
            return TransactionResponse(
                tx_hash=tx.get('hash', 'unknown'),
               block_number=int(tx.get('blockNumber', 0)),
               timestamp=datetime.fromtimestamp(int(tx.get('timeStamp', 0)) if tx.get('timeStamp') else 0),
               from_address=tx.get('from', '').lower(),
               to_address=tx.get('to', '').lower(),
               transaction_type=TransactionType.ERC20,
               token_address=tx.get('contractAddress', '').lower(),
               token_symbol=tx.get('tokenSymbol', ''),
               token_name=tx.get('tokenName', ''),
               value="0",
               gas_fee="0"
           )
   
    def _process_nft_transaction(self, tx: Dict) -> TransactionResponse:
        """Process ERC-721/ERC-1155 NFT transaction"""
        try:
            return TransactionResponse(
                tx_hash=tx.get('hash', ''),
                block_number=int(tx.get('blockNumber', 0)),
                timestamp=datetime.fromtimestamp(int(tx.get('timeStamp', 0))),
                from_address=tx.get('from', '').lower(),
                to_address=tx.get('to', '').lower(),
                transaction_type=TransactionType.ERC721,
                token_address=tx.get('contractAddress', '').lower(),
                token_symbol=tx.get('tokenSymbol', ''),
                token_name=tx.get('tokenName', ''),
                token_id=tx.get('tokenID', ''),
                value="1",  # NFTs typically have value of 1
                gas_fee=str(Decimal(tx.get('gasUsed', 0)) * Decimal(tx.get('gasPrice', 0)) / Decimal(10**18))
            )
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Error processing NFT transaction: {e}, tx: {tx}")
            return TransactionResponse(
                tx_hash=tx.get('hash', 'unknown'),
                block_number=int(tx.get('blockNumber', 0)),
                timestamp=datetime.fromtimestamp(int(tx.get('timeStamp', 0)) if tx.get('timeStamp') else 0),
                from_address=tx.get('from', '').lower(),
                to_address=tx.get('to', '').lower(),
                transaction_type=TransactionType.ERC721,
                token_address=tx.get('contractAddress', '').lower(),
                token_symbol=tx.get('tokenSymbol', ''),
                token_name=tx.get('tokenName', ''),
                token_id=tx.get('tokenID', ''),
                value="1",
                gas_fee="0"
            )

    
    async def _log_api_usage(self, wallet_address: str, endpoint: str):
        """Log API usage to database"""
        try:
            query = """
                INSERT INTO api_usage (wallet_address, endpoint, request_timestamp)
                VALUES (:wallet_address, :endpoint, :timestamp)
            """
            values = {
                "wallet_address": wallet_address,
                "endpoint": endpoint,
                "timestamp": datetime.utcnow()
            }
            await database.execute(query, values)
        except Exception as e:
            logger.warning(f"Failed to log API usage: {e}")
    
    async def get_transaction_summary(self, wallet_address: str) -> Dict[str, Any]:
        """Get transaction summary statistics for a wallet"""
        
        validated_address = AddressValidator.validate_ethereum_address(wallet_address)
        
        try:
            result = await self.get_transactions(
                wallet_address=validated_address,
                page=1,
                page_size=10000  # Get all for summary (if not hitting pagination limit)
            )
            
            # Check if we hit the large dataset error
            if result.get("error") == "large_dataset":
                return {
                    "wallet_address": validated_address,
                    "error": "large_dataset",
                    "message": "Cannot generate summary for addresses with large transaction counts",
                    "suggestion": "Use the reports endpoint for complete transaction analysis"
                }
            
            transactions = result['transactions']
            
            # Calculate summary statistics
            total_transactions = len(transactions)
            transaction_type_counts = {}
            total_gas_fees = 0
            
            for tx in transactions:
                # Count by type
                tx_type = tx.transaction_type.value if hasattr(tx.transaction_type, 'value') else str(tx.transaction_type)
                transaction_type_counts[tx_type] = transaction_type_counts.get(tx_type, 0) + 1
                
                # Sum gas fees
                try:
                    total_gas_fees += float(tx.gas_fee)
                except (ValueError, TypeError):
                    pass
            
            return {
                "wallet_address": validated_address,
                "total_transactions": total_transactions,
                "transaction_type_breakdown": transaction_type_counts,
                "total_gas_fees_eth": round(total_gas_fees, 6),
                "date_range": {
                    "earliest": min(tx.timestamp for tx in transactions).isoformat() if transactions else None,
                    "latest": max(tx.timestamp for tx in transactions).isoformat() if transactions else None
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating transaction summary for {validated_address}: {str(e)}")
            raise Exception(f"Failed to generate transaction summary: {str(e)}")
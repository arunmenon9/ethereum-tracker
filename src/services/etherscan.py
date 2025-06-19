import aiohttp
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import time
import random

from src.config import get_settings
from src.cache import cache_manager
from src.utils.validators import AddressValidator

settings = get_settings()
logger = logging.getLogger(__name__)

class PaginationLimitExceeded(Exception):
    """Raised when Etherscan pagination limit is exceeded"""
    pass

class EtherscanClient:
    def __init__(self):
        self.api_key = settings.ETHERSCAN_API_KEY
        self.base_url = settings.ETHERSCAN_BASE_URL
        self.rate_limiter = RateLimiter(settings.ETHERSCAN_RATE_LIMIT)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=100, limit_per_host=10)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _make_request(self, params: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        """Make API request with retry logic and rate limiting"""
        params['apikey'] = self.api_key
        
        for attempt in range(max_retries + 1):
            await self.rate_limiter.acquire()
            
            try:
                async with self.session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Check for pagination limit error in the message even with status '1'
                        message = data.get('message', '').lower()
                        if 'result window is too large' in message or 'offset size must be less than or equal to 10000' in message:
                            raise PaginationLimitExceeded(data.get('message', 'Pagination limit exceeded'))
                        
                        if data.get('status') == '1':
                            return data
                        elif 'rate limit' in message:
                            raise aiohttp.ClientResponseError(
                                request_info=response.request_info,
                                history=response.history,
                                status=429
                            )
                        else:
                            logger.warning(f"API returned error: {data.get('message')}")
                            return data
                    elif response.status == 429:
                        # Rate limit exceeded
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"Rate limit exceeded, waiting {wait_time:.2f}s")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        response.raise_for_status()
                        
            except PaginationLimitExceeded:
                # Re-raise pagination errors immediately
                raise
            except asyncio.TimeoutError:
                if attempt == max_retries:
                    raise Exception("Request timeout after retries")
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(wait_time)
            except aiohttp.ClientError as e:
                if attempt == max_retries:
                    raise Exception(f"Network error: {str(e)}")
                await asyncio.sleep(2 ** attempt)
        
        raise Exception("Failed to complete request after retries")

    async def get_current_block_number(self) -> int:
        """Get the current block number"""
        cache_key = cache_manager.get_cache_key("current_block")
        cached_result = await cache_manager.get(cache_key)
        
        if cached_result:
            return cached_result
        
        params = {
            'chainid': 1,
            'module': 'proxy',
            'action': 'eth_blockNumber'
        }
        
        try:
            result = await self._make_request(params)
            block_number = int(result['result'], 16) if result.get('result') else 0
            
            # Cache for 30 seconds
            await cache_manager.set(cache_key, block_number, 30)
            return block_number
        except Exception as e:
            logger.warning(f"Failed to get current block number: {e}")
            return 0
    
    async def get_normal_transactions(self, address: str, start_block: int = 0, end_block: int = 99999999) -> List[Dict]:
        """Get normal ETH transactions"""
        cache_key = cache_manager.get_cache_key("eth_tx", address, start_block, end_block)
        cached_result = await cache_manager.get(cache_key)
        
        if cached_result:
            return cached_result
        
        params = {
            'chainid': 1,
            'module': 'account',
            'action': 'txlist',
            'address': address,
            'startblock': start_block,
            'endblock': end_block,
            'sort': 'asc'
        }
        
        all_transactions = []
        page = 1
        max_offset = 1000  # Reduced to avoid pagination limit
        
        while True:
            params.update({'page': page, 'offset': max_offset})
            
            # Check if we're approaching the pagination limit BEFORE making the request
            if page * max_offset > 9000:  # Stop before hitting 10,000 limit
                logger.warning(f"Approaching pagination limit for address {address} at page {page}")
                raise PaginationLimitExceeded(f"Too many transactions for standard pagination. Address {address} has more than {9000} transactions.")
            
            try:
                result = await self._make_request(params)
            except PaginationLimitExceeded:
                # If we get the error from API, re-raise it
                raise
            
            if not result.get('result'):
                break
            
            transactions = result['result']
            if not transactions:
                break
                
            all_transactions.extend(transactions)
            
            if len(transactions) < max_offset:  # Last page
                break
                
            page += 1
        
        await cache_manager.set(cache_key, all_transactions, settings.CACHE_TTL_TRANSACTIONS)
        return all_transactions   
 
    async def get_internal_transactions(self, address: str, start_block: int = 0, end_block: int = 99999999) -> List[Dict]:
        """Get internal transactions"""
        cache_key = cache_manager.get_cache_key("internal_tx", address, start_block, end_block)
        cached_result = await cache_manager.get(cache_key)
        
        if cached_result:
            return cached_result
        
        params = {
            'chainid': 1,
            'module': 'account',
            'action': 'txlistinternal',
            'address': address,
            'startblock': start_block,
            'endblock': end_block,
            'sort': 'asc'
        }
        
        all_transactions = []
        page = 1
        max_offset = 1000
        
        while True:
            params.update({'page': page, 'offset': max_offset})
            
            # Check pagination limit before request
            if page * max_offset > 9000:
                logger.warning(f"Approaching pagination limit for internal transactions of address {address}")
                raise PaginationLimitExceeded(f"Too many internal transactions for standard pagination. Address {address} has more than {9000} internal transactions.")
            
            try:
                result = await self._make_request(params)
            except PaginationLimitExceeded:
                raise
            
            if not result.get('result'):
                break
            
            transactions = result['result']
            if not transactions:
                break
                
            all_transactions.extend(transactions)
            
            if len(transactions) < max_offset:
                break
                
            page += 1
        
        await cache_manager.set(cache_key, all_transactions, settings.CACHE_TTL_TRANSACTIONS)
        return all_transactions
   
    async def get_token_transfers(self, address: str, start_block: int = 0, end_block: int = 99999999, contract_address: Optional[str] = None) -> List[Dict]:
        """Get ERC-20 token transfers"""
        cache_key = cache_manager.get_cache_key("token_tx", address, contract_address or "all")
        cached_result = await cache_manager.get(cache_key)
        
        if cached_result:
            return cached_result
        
        params = {
            'chainid': 1,
            'module': 'account',
            'action': 'tokentx',
            'address': address,
            'startblock': start_block,
            'endblock': end_block,
            'sort': 'asc'
        }
        
        if contract_address:
            params['contractaddress'] = contract_address
        
        all_transactions = []
        page = 1
        max_offset = 1000
        
        while True:
            params.update({'page': page, 'offset': max_offset})
            
            # Check pagination limit before request
            if page * max_offset > 9000:
                logger.warning(f"Approaching pagination limit for token transfers of address {address}")
                raise PaginationLimitExceeded(f"Too many token transfers for standard pagination. Address {address} has more than {9000} token transfers.")
            
            try:
                result = await self._make_request(params)
            except PaginationLimitExceeded:
                raise
            
            if not result.get('result'):
                break
            
            transactions = result['result']
            if not transactions:
                break
                
            all_transactions.extend(transactions)
            
            if len(transactions) < max_offset:
                break
                
            page += 1
        
        await cache_manager.set(cache_key, all_transactions, settings.CACHE_TTL_TRANSACTIONS)
        return all_transactions   

    async def get_nft_transfers(self, address: str, start_block: int = 0, end_block: int = 99999999, contract_address: Optional[str] = None) -> List[Dict]:
        """Get ERC-721 NFT transfers"""
        cache_key = cache_manager.get_cache_key("nft_tx", address, contract_address or "all")
        cached_result = await cache_manager.get(cache_key)
        
        if cached_result:
            return cached_result
        
        params = {
            'chainid': 1,
            'module': 'account',
            'action': 'tokennfttx',
            'address': address,
            'startblock': start_block,
            'endblock': end_block,
            'sort': 'asc'
        }
        
        if contract_address:
            params['contractaddress'] = contract_address
        
        all_transactions = []
        page = 1
        max_offset = 1000
        
        while True:
            params.update({'page': page, 'offset': max_offset})
            
            # Check pagination limit before request
            if page * max_offset > 9000:
                logger.warning(f"Approaching pagination limit for NFT transfers of address {address}")
                raise PaginationLimitExceeded(f"Too many NFT transfers for standard pagination. Address {address} has more than {9000} NFT transfers.")
            
            try:
                result = await self._make_request(params)
            except PaginationLimitExceeded:
                raise
            
            if not result.get('result'):
                break
            
            transactions = result['result']
            if not transactions:
                break
                
            all_transactions.extend(transactions)
            
            if len(transactions) < max_offset:
                break
                
            page += 1
        
        await cache_manager.set(cache_key, all_transactions, settings.CACHE_TTL_TRANSACTIONS)
        return all_transactions
      
    async def get_all_transactions(self, address: str) -> Dict[str, List[Dict]]:
        """Get all transaction types for an address (may hit pagination limits)"""
        # Use asyncio.gather for concurrent requests
        normal_tx_task = self.get_normal_transactions(address)
        internal_tx_task = self.get_internal_transactions(address)
        token_tx_task = self.get_token_transfers(address)
        nft_tx_task = self.get_nft_transfers(address)
        
        normal_tx, internal_tx, token_tx, nft_tx = await asyncio.gather(
            normal_tx_task, internal_tx_task, token_tx_task, nft_tx_task,
            # return_exceptions=True
        )

        return {
            'normal': normal_tx if not isinstance(normal_tx, Exception) else [],
            'internal': internal_tx if not isinstance(internal_tx, Exception) else [],
            'token': token_tx if not isinstance(token_tx, Exception) else [],
            'nft': nft_tx if not isinstance(nft_tx, Exception) else []
        }
    
    async def get_all_transactions_block_range(self, address: str, start_block: int, end_block: int) -> Dict[str, List[Dict]]:
        """Get all transaction types for an address within a specific block range"""
        # Use asyncio.gather for concurrent requests
        normal_tx_task = self.get_normal_transactions(address, start_block, end_block)
        internal_tx_task = self.get_internal_transactions(address, start_block, end_block)
        token_tx_task = self.get_token_transfers(address, start_block, end_block)
        nft_tx_task = self.get_nft_transfers(address, start_block, end_block)
        
        normal_tx, internal_tx, token_tx, nft_tx = await asyncio.gather(
            normal_tx_task, internal_tx_task, token_tx_task, nft_tx_task,
             return_exceptions=True
        )


        return {
            'normal': normal_tx if not isinstance(normal_tx, Exception) else [],
            'internal': internal_tx if not isinstance(internal_tx, Exception) else [],
            'token': token_tx if not isinstance(token_tx, Exception) else [],
            'nft': nft_tx if not isinstance(nft_tx, Exception) else []
        }

class RateLimiter:
    def __init__(self, calls_per_second: float):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_called = 0.0
    
    async def acquire(self):
        """Acquire rate limit token"""
        now = time.time()
        elapsed = now - self.last_called
        
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            await asyncio.sleep(sleep_time)
        
        self.last_called = time.time()
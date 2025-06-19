import re
from fastapi import HTTPException

class AddressValidator:
    """Ethereum address validation utilities"""
    
    ETHEREUM_ADDRESS_PATTERN = re.compile(r'^0x[a-fA-F0-9]{40}$')
    TRANSACTION_HASH_PATTERN = re.compile(r'^0x[a-fA-F0-9]{64}$')
    
    @classmethod
    def validate_ethereum_address(cls, address: str) -> str:
        """Validate and normalize Ethereum address with detailed error messages"""
        if not address:
            raise ValueError("Address cannot be empty")
        
        if not address.startswith('0x'):
            raise ValueError("Ethereum address must start with '0x'")
        
        # Check length first
        hex_part = address[2:]
        if len(hex_part) != 40:
            raise ValueError(
                f"Ethereum address must have exactly 40 hexadecimal characters after '0x'. "
                f"Provided address has {len(hex_part)} characters. "
                f"Example of valid address: 0x742d35Cc63aB4747B8bc21bB6c2d65bb0E4e8b5d"
            )
        
        # Check if all characters are valid hex
        if not cls.ETHEREUM_ADDRESS_PATTERN.match(address):
            raise ValueError(
                "Invalid Ethereum address format. "
                "Address must contain only hexadecimal characters (0-9, a-f, A-F) after '0x'"
            )
        
        return address.lower()
    
    @classmethod
    def validate_transaction_hash(cls, tx_hash: str) -> str:
        """Validate and normalize transaction hash"""
        if not tx_hash:
            raise ValueError("Transaction hash cannot be empty")
        
        if not tx_hash.startswith('0x'):
            raise ValueError("Transaction hash must start with '0x'")
        
        hex_part = tx_hash[2:]
        if len(hex_part) != 64:
            raise ValueError(
                f"Transaction hash must have exactly 64 hexadecimal characters after '0x'. "
                f"Provided hash has {len(hex_part)} characters."
            )
        
        if not cls.TRANSACTION_HASH_PATTERN.match(tx_hash):
            raise ValueError(
                "Invalid transaction hash format. "
                "Hash must contain only hexadecimal characters (0-9, a-f, A-F) after '0x'"
            )
        
        return tx_hash.lower()
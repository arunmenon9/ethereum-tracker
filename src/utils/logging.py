import logging
import sys
from src.config import get_settings

def setup_logging():
    """Setup structured logging configuration"""
    settings = get_settings()
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Suppress noisy loggers
    logging.getLogger("databases").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
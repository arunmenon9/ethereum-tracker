from sqlalchemy import create_engine, MetaData, Column, Integer, String, BigInteger, DateTime, Text, Numeric, Index
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from databases import Database
from datetime import datetime
from src.config import get_settings

settings = get_settings()

# Async database connection
database = Database(settings.DATABASE_URL)

# SQLAlchemy setup
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()
metadata = MetaData()

# Database Models
class Block(Base):
    __tablename__ = "blocks"
    
    id = Column(Integer, primary_key=True)
    block_number = Column(BigInteger, nullable=False, unique=True, index=True)
    block_hash = Column(String(66), nullable=False, unique=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    gas_limit = Column(BigInteger, nullable=False)
    gas_used = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True)
    tx_hash = Column(String(66), nullable=False, unique=True, index=True)
    block_number = Column(BigInteger, nullable=False, index=True)
    from_address = Column(String(42), nullable=False, index=True)
    to_address = Column(String(42), index=True)
    value = Column(Numeric(78), nullable=False)  # Wei amount
    gas_limit = Column(BigInteger, nullable=False)
    gas_price = Column(BigInteger, nullable=False)
    gas_used = Column(BigInteger)
    transaction_type = Column(String(20), nullable=False, default="ETH")  # ETH, ERC20, ERC721, etc.
    token_address = Column(String(42))  # For token transactions
    token_symbol = Column(String(20))
    token_name = Column(String(100))
    token_id = Column(String(78))  # For NFTs
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Composite indexes for performance
    __table_args__ = (
        Index('idx_tx_from_timestamp', 'from_address', 'timestamp'),
        Index('idx_tx_to_timestamp', 'to_address', 'timestamp'),
        Index('idx_tx_type_timestamp', 'transaction_type', 'timestamp'),
    )

class APIUsage(Base):
    __tablename__ = "api_usage"
    
    id = Column(Integer, primary_key=True)
    wallet_address = Column(String(42), nullable=False, index=True)
    endpoint = Column(String(100), nullable=False)
    request_timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    response_time_ms = Column(Integer)
    status_code = Column(Integer)
    ip_address = Column(String(45))
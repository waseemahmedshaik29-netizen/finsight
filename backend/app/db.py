import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

load_dotenv()
URL = os.getenv("DATABASE_URL", "sqlite:///./finsight.db")
engine = create_engine(
    URL,
    connect_args={"check_same_thread": False} if URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)
if URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def enable_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")


class Base(DeclarativeBase):
    pass


class Portfolio(Base):
    __tablename__ = "portfolios"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    benchmark: Mapped[str] = mapped_column(String(12), default="SPY")
    cash: Mapped[float] = mapped_column(Float, default=0)
    positions: Mapped[list["Position"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("portfolio_id", "ticker"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE")
    )
    ticker: Mapped[str] = mapped_column(String(12))
    quantity: Mapped[float] = mapped_column(Float)
    cost_basis: Mapped[float] = mapped_column(Float)


class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    payload: Mapped[dict] = mapped_column(JSON)


class Cache(Base):
    __tablename__ = "cache"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


Session = sessionmaker(engine, expire_on_commit=False)


def session():
    with Session() as db:
        yield db

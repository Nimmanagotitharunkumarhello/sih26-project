"""SQLAlchemy models for the synthetic ownership register.

Every row here is fabricated demo data. Owner names, Aadhaar references and
transactions are generated, not sourced from any real record.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Parcel(Base):
    """One vertically-delimited property: a single unit on a single floor."""

    __tablename__ = "parcels"

    ulpin_3d: Mapped[str] = mapped_column(String(32), primary_key=True)
    parent_ulpin_2d: Mapped[str] = mapped_column(String(14), index=True)
    osm_id: Mapped[str] = mapped_column(String(32), index=True)
    #: "<base>-Fnn" -- lets the API fetch a whole floor with one indexed lookup.
    floor_prefix: Mapped[str] = mapped_column(String(20), index=True)

    floor_number: Mapped[int] = mapped_column(Integer)
    unit_number: Mapped[int] = mapped_column(Integer)
    unit_type: Mapped[str] = mapped_column(String(16))
    area_sqft: Mapped[float] = mapped_column(Float)
    base_z: Mapped[float] = mapped_column(Float)
    floor_height: Mapped[float] = mapped_column(Float)

    owner_name: Mapped[str] = mapped_column(String(120))
    #: Masked on purpose -- only the last four digits are ever stored.
    owner_aadhaar_ref: Mapped[str] = mapped_column(String(16))
    purchase_date: Mapped[date] = mapped_column(Date)
    encumbrance_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    encumbrance_note: Mapped[str | None] = mapped_column(String(200), nullable=True)

    #: GeoJSON Polygon, stored as text -- SQLite has no native geometry type and
    #: the prototype never queries by unit geometry, only by ULPIN.
    geometry: Mapped[str] = mapped_column(Text)

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="parcel",
        cascade="all, delete-orphan",
        order_by="Transaction.transaction_date.desc()",
    )


class Transaction(Base):
    """A synthetic ownership event against a parcel."""

    __tablename__ = "transactions"

    transaction_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ulpin_3d: Mapped[str] = mapped_column(ForeignKey("parcels.ulpin_3d"), index=True)

    transaction_type: Mapped[str] = mapped_column(String(20))  # sale | inheritance | mortgage
    transaction_date: Mapped[date] = mapped_column(Date)
    amount_inr: Mapped[float | None] = mapped_column(Float, nullable=True)
    from_party: Mapped[str | None] = mapped_column(String(120), nullable=True)
    to_party: Mapped[str] = mapped_column(String(120))

    parcel: Mapped[Parcel] = relationship(back_populates="transactions")

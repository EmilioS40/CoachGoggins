from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ActivityRecord(Base):
    __tablename__ = "activity_records"

    id: Mapped[int] = mapped_column(primary_key=True)

    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    record_index: Mapped[int] = mapped_column(Integer, nullable=False)

    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    distance_m: Mapped[float | None] = mapped_column(Float)

    latitude_semicircles: Mapped[int | None] = mapped_column(Integer)
    longitude_semicircles: Mapped[int | None] = mapped_column(Integer)

    altitude_m: Mapped[float | None] = mapped_column(Float)
    speed_mps: Mapped[float | None] = mapped_column(Float)

    heart_rate_bpm: Mapped[int | None] = mapped_column(Integer)
    cadence: Mapped[float | None] = mapped_column(Float)

    power_w: Mapped[float | None] = mapped_column(Float)
    accumulated_power: Mapped[float | None] = mapped_column(Float)

    stance_time_ms: Mapped[float | None] = mapped_column(Float)
    step_length_mm: Mapped[float | None] = mapped_column(Float)

    vertical_oscillation_mm: Mapped[float | None] = mapped_column(Float)
    vertical_ratio_pct: Mapped[float | None] = mapped_column(Float)

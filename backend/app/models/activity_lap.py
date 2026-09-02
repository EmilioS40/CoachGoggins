from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ActivityLap(Base):
    __tablename__ = "activity_laps"

    id: Mapped[int] = mapped_column(primary_key=True)

    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    lap_index: Mapped[int] = mapped_column(Integer, nullable=False)

    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    total_distance_m: Mapped[float | None] = mapped_column(Float)
    total_timer_time_s: Mapped[float | None] = mapped_column(Float)
    total_elapsed_time_s: Mapped[float | None] = mapped_column(Float)

    total_ascent_m: Mapped[float | None] = mapped_column(Float)
    total_descent_m: Mapped[float | None] = mapped_column(Float)

    avg_heart_rate: Mapped[float | None] = mapped_column(Float)
    max_heart_rate: Mapped[float | None] = mapped_column(Float)

    avg_cadence: Mapped[float | None] = mapped_column(Float)
    max_cadence: Mapped[float | None] = mapped_column(Float)

    avg_power: Mapped[float | None] = mapped_column(Float)
    max_power: Mapped[float | None] = mapped_column(Float)
    normalized_power: Mapped[float | None] = mapped_column(Float)

    avg_speed_mps: Mapped[float | None] = mapped_column(Float)
    max_speed_mps: Mapped[float | None] = mapped_column(Float)

    avg_stance_time_ms: Mapped[float | None] = mapped_column(Float)
    avg_step_length_mm: Mapped[float | None] = mapped_column(Float)

    avg_vertical_oscillation_mm: Mapped[float | None] = mapped_column(Float)
    avg_vertical_ratio_pct: Mapped[float | None] = mapped_column(Float)

    total_calories: Mapped[float | None] = mapped_column(Float)

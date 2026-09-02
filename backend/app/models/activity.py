from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)

    garmin_activity_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )

    garmin_uuid: Mapped[str | None] = mapped_column(String(100))

    name: Mapped[str | None] = mapped_column(String(255))
    sport_type: Mapped[str | None] = mapped_column(String(100))

    start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    distance_m: Mapped[float | None] = mapped_column(Float)

    moving_time_s: Mapped[float | None] = mapped_column(Float)
    elapsed_time_s: Mapped[float | None] = mapped_column(Float)
    duration_s: Mapped[float | None] = mapped_column(Float)

    elevation_gain_m: Mapped[float | None] = mapped_column(Float)
    elevation_loss_m: Mapped[float | None] = mapped_column(Float)

    average_speed_mps: Mapped[float | None] = mapped_column(Float)
    max_speed_mps: Mapped[float | None] = mapped_column(Float)

    average_heartrate: Mapped[float | None] = mapped_column(Float)
    max_heartrate: Mapped[float | None] = mapped_column(Float)

    average_cadence_spm: Mapped[float | None] = mapped_column(Float)

    average_power_w: Mapped[float | None] = mapped_column(Float)
    max_power_w: Mapped[float | None] = mapped_column(Float)
    normalized_power_w: Mapped[float | None] = mapped_column(Float)

    training_load: Mapped[float | None] = mapped_column(Float)
    aerobic_training_effect: Mapped[float | None] = mapped_column(Float)
    anaerobic_training_effect: Mapped[float | None] = mapped_column(Float)

    vo2max: Mapped[float | None] = mapped_column(Float)

    calories: Mapped[float | None] = mapped_column(Float)

    fit_file_path: Mapped[str | None] = mapped_column(Text)

    raw_summary_json: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

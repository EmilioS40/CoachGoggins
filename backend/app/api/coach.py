from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy import func, select

from pathlib import Path
from fastapi.responses import FileResponse

from app.db.session import SessionLocal
from app.models.activity import Activity
from app.models.activity_lap import ActivityLap
from app.models.activity_record import ActivityRecord
from app.core.security import verify_coach_api_key

router = APIRouter(
    prefix="/api/coach",
    tags=["coach"],
    dependencies=[Depends(verify_coach_api_key)],
)


@router.get("/export/excel")
def coach_excel_export():
    path = Path("/var/lib/sport/exports/Sport_report.xlsx")

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Excel export not found",
        )

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="Sport_report.xlsx",
    )

def activity_summary(activity: Activity):

    pace_s_per_km = None

    duration = (
        activity.moving_time_s
        or activity.duration_s
        or 0
    )

    if activity.distance_m and duration:
        pace_s_per_km = (
            duration
            / (activity.distance_m / 1000)
        )

    return {
        "garmin_id": activity.garmin_activity_id,

        "date": (
            activity.start_date.isoformat()
            if activity.start_date
            else None
        ),

        "name": activity.name,
        "sport_type": activity.sport_type,

        "distance_km": round(
            (activity.distance_m or 0) / 1000,
            2,
        ),

        "duration_min": round(
            duration / 60,
            1,
        ),

        "pace_s_per_km": (
            round(pace_s_per_km, 1)
            if pace_s_per_km
            else None
        ),

        "elevation_gain_m": activity.elevation_gain_m,
        "elevation_loss_m": activity.elevation_loss_m,

        "avg_hr": activity.average_heartrate,
        "max_hr": activity.max_heartrate,

        "avg_cadence_spm": (
            activity.average_cadence_spm
        ),

        "avg_power_w": activity.average_power_w,
        "max_power_w": activity.max_power_w,

        "normalized_power_w": (
            activity.normalized_power_w
        ),

        "training_load": activity.training_load,

        "aerobic_training_effect": (
            activity.aerobic_training_effect
        ),

        "anaerobic_training_effect": (
            activity.anaerobic_training_effect
        ),

        "vo2max": activity.vo2max,

        "calories": activity.calories,
    }


@router.get("/context")
def coach_context(
    days: int = Query(
        default=42,
        ge=7,
        le=365,
    )
):

    db = SessionLocal()

    try:

        since = (
            datetime.now(timezone.utc)
            - timedelta(days=days)
        )

        activities = db.scalars(
            select(Activity)
            .where(Activity.start_date >= since)
            .order_by(Activity.start_date.desc())
        ).all()

        total_distance = sum(
            a.distance_m or 0
            for a in activities
        )

        total_duration = sum(
            a.moving_time_s or a.duration_s or 0
            for a in activities
        )

        total_elevation = sum(
            a.elevation_gain_m or 0
            for a in activities
        )

        total_load = sum(
            a.training_load or 0
            for a in activities
        )

        weekly_query = (
            select(
                func.date_trunc(
                    "week",
                    Activity.start_date,
                ).label("week"),

                func.count(
                    Activity.id
                ).label("activities"),

                func.sum(
                    Activity.distance_m
                ).label("distance_m"),

                func.sum(
                    Activity.moving_time_s
                ).label("moving_time_s"),

                func.sum(
                    Activity.elevation_gain_m
                ).label("elevation_gain_m"),

                func.sum(
                    Activity.training_load
                ).label("training_load"),
            )
            .where(Activity.start_date >= since)
            .group_by("week")
            .order_by("week")
        )

        weekly_rows = db.execute(
            weekly_query
        ).all()

        weekly = []

        for row in weekly_rows:

            weekly.append({
                "week": row.week.isoformat(),

                "activities": row.activities,

                "distance_km": round(
                    (row.distance_m or 0) / 1000,
                    2,
                ),

                "duration_h": round(
                    (row.moving_time_s or 0) / 3600,
                    2,
                ),

                "elevation_gain_m": round(
                    row.elevation_gain_m or 0
                ),

                "training_load": round(
                    row.training_load or 0,
                    1,
                ),
            })

        return {
            "generated_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),

            "period_days": days,

            "totals": {
                "activities": len(activities),

                "distance_km": round(
                    total_distance / 1000,
                    2,
                ),

                "duration_h": round(
                    total_duration / 3600,
                    2,
                ),

                "elevation_gain_m": round(
                    total_elevation
                ),

                "training_load": round(
                    total_load,
                    1,
                ),
            },

            "weekly": weekly,

            "recent_activities": [
                activity_summary(a)
                for a in activities[:10]
            ],
        }

    finally:
        db.close()


@router.get("/activity/latest")
def latest_activity(
    sport_type: str | None = None,
):

    db = SessionLocal()

    try:

        query = select(Activity)

        if sport_type:
            query = query.where(
                func.lower(Activity.sport_type).contains(
                    sport_type.lower()
                )
            )

        activity = db.scalar(
            query.order_by(
                Activity.start_date.desc()
            )
            .limit(1)
        )

        if not activity:
            raise HTTPException(
                status_code=404,
                detail="No matching activity found",
            )

        return activity_summary(activity)

    finally:
        db.close()


@router.get("/activity/{garmin_id}")
def activity_detail(
    garmin_id: int,
):

    db = SessionLocal()

    try:

        activity = db.scalar(
            select(Activity).where(
                Activity.garmin_activity_id
                == garmin_id
            )
        )

        if not activity:
            raise HTTPException(
                status_code=404,
                detail="Activity not found",
            )

        laps = db.scalars(
            select(ActivityLap)
            .where(
                ActivityLap.activity_id
                == activity.id
            )
            .order_by(
                ActivityLap.lap_index
            )
        ).all()

        lap_data = []

        for lap in laps:

            pace_s_per_km = None

            if (
                lap.total_distance_m
                and lap.total_timer_time_s
            ):
                pace_s_per_km = (
                    lap.total_timer_time_s
                    / (
                        lap.total_distance_m
                        / 1000
                    )
                )

            lap_data.append({
                "lap": lap.lap_index + 1,

                "distance_m": (
                    lap.total_distance_m
                ),

                "duration_s": (
                    lap.total_timer_time_s
                ),

                "pace_s_per_km": (
                    round(
                        pace_s_per_km,
                        1,
                    )
                    if pace_s_per_km
                    else None
                ),

                "ascent_m": (
                    lap.total_ascent_m
                ),

                "descent_m": (
                    lap.total_descent_m
                ),

                "avg_hr": (
                    lap.avg_heart_rate
                ),

                "max_hr": (
                    lap.max_heart_rate
                ),

                "avg_cadence_spm": (
                    lap.avg_cadence
                ),

                "avg_power_w": (
                    lap.avg_power
                ),

                "normalized_power_w": (
                    lap.normalized_power
                ),

                "avg_speed_mps": (
                    lap.avg_speed_mps
                ),

                "stance_time_ms": (
                    lap.avg_stance_time_ms
                ),

                "step_length_mm": (
                    lap.avg_step_length_mm
                ),

                "vertical_oscillation_mm": (
                    lap.avg_vertical_oscillation_mm
                ),

                "vertical_ratio_pct": (
                    lap.avg_vertical_ratio_pct
                ),
            })

        return {
            "activity": activity_summary(
                activity
            ),

            "lap_count": len(lap_data),

            "laps": lap_data,

            "records_available": db.scalar(
                select(
                    func.count(
                        ActivityRecord.id
                    )
                )
                .where(
                    ActivityRecord.activity_id
                    == activity.id
                )
            ),
        }

    finally:
        db.close()


@router.get("/activity/{garmin_id}/records")
def activity_records(
    garmin_id: int,

    every: int = Query(
        default=1,
        ge=1,
        le=60,
        description=(
            "Return one record every N samples"
        ),
    ),
):

    db = SessionLocal()

    try:

        activity = db.scalar(
            select(Activity).where(
                Activity.garmin_activity_id
                == garmin_id
            )
        )

        if not activity:
            raise HTTPException(
                status_code=404,
                detail="Activity not found",
            )

        records = db.scalars(
            select(ActivityRecord)
            .where(
                ActivityRecord.activity_id
                == activity.id
            )
            .order_by(
                ActivityRecord.record_index
            )
        ).all()

        result = []

        for record in records[::every]:

            lat = None
            lon = None

            if record.latitude_semicircles is not None:
                lat = (
                    record.latitude_semicircles
                    * 180
                    / (2 ** 31)
                )

            if record.longitude_semicircles is not None:
                lon = (
                    record.longitude_semicircles
                    * 180
                    / (2 ** 31)
                )

            result.append({
                "index": (
                    record.record_index
                ),

                "timestamp": (
                    record.timestamp.isoformat()
                    if record.timestamp
                    else None
                ),

                "distance_m": (
                    record.distance_m
                ),

                "latitude": lat,
                "longitude": lon,

                "altitude_m": (
                    record.altitude_m
                ),

                "speed_mps": (
                    record.speed_mps
                ),

                "heart_rate_bpm": (
                    record.heart_rate_bpm
                ),

                "cadence_spm": (
                    record.cadence
                ),

                "power_w": (
                    record.power_w
                ),

                "stance_time_ms": (
                    record.stance_time_ms
                ),

                "step_length_mm": (
                    record.step_length_mm
                ),

                "vertical_oscillation_mm": (
                    record.vertical_oscillation_mm
                ),

                "vertical_ratio_pct": (
                    record.vertical_ratio_pct
                ),
            })

        return {
            "garmin_id": garmin_id,

            "original_records": len(records),

            "sampling": every,

            "returned_records": len(result),

            "records": result,
        }

    finally:
        db.close()

import argparse
import io
import json
import time
import zipfile

from datetime import datetime, timezone
from pathlib import Path

from garminconnect import Garmin
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.activity import Activity
from app.services.fit_parser import (
    decode_fit,
    build_laps,
    build_records,
)


TOKENSTORE = "/var/lib/sport/garmin"
DATA_ROOT = Path("/var/lib/sport/data/activities")

PAGE_SIZE = 25


def garmin_call(func, *args, **kwargs):
    """Retry simple en cas de rate limiting Garmin."""

    for attempt in range(6):

        try:
            return func(*args, **kwargs)

        except Exception as exc:

            message = str(exc)

            if "429" not in message:
                raise

            wait = min(300, 20 * (2 ** attempt))

            print(f"Garmin rate limit. Attente {wait}s...")
            time.sleep(wait)

    raise RuntimeError("Garmin toujours indisponible après retries")


def save_json(path: Path, data):

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )


def download_fit(api, garmin_id: int, activity_dir: Path):

    fit_path = activity_dir / f"{garmin_id}.fit"
    zip_path = activity_dir / f"{garmin_id}.zip"

    if fit_path.exists():
        return fit_path

    raw = garmin_call(
        api.download_activity,
        garmin_id,
        dl_fmt=api.ActivityDownloadFormat.ORIGINAL,
    )

    activity_dir.mkdir(parents=True, exist_ok=True)

    zip_path.write_bytes(raw)

    with zipfile.ZipFile(io.BytesIO(raw)) as archive:

        fit_names = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".fit")
        ]

        if not fit_names:
            raise RuntimeError(
                f"Aucun FIT dans l'activité {garmin_id}"
            )

        fit_path.write_bytes(
            archive.read(fit_names[0])
        )

    return fit_path


def parse_start_date(summary):

    value = summary.get("startTimeGMT")

    if not value:
        return None

    return datetime.strptime(
        value,
        "%Y-%m-%d %H:%M:%S",
    ).replace(tzinfo=timezone.utc)


def sync_activity(api, summary):

    garmin_id = int(summary["activityId"])

    db = SessionLocal()

    try:

        existing = db.scalar(
            select(Activity).where(
                Activity.garmin_activity_id == garmin_id
            )
        )

        if existing:
            print(f"[SKIP] {garmin_id}")
            return False

        name = summary.get("activityName")

        print(f"[SYNC] {garmin_id} - {name}")

        activity_dir = DATA_ROOT / str(garmin_id)
        activity_dir.mkdir(parents=True, exist_ok=True)

        # Liste Garmin brute
        save_json(
            activity_dir / "summary.json",
            summary,
        )

        # Endpoint individuel Garmin.
        full_activity = garmin_call(
            api.get_activity,
            garmin_id,
        )

        save_json(
            activity_dir / "activity.json",
            full_activity,
        )

        # FIT original
        fit_path = download_fit(
            api,
            garmin_id,
            activity_dir,
        )

        activity_type = summary.get(
            "activityType",
            {},
        ).get("typeKey")

        activity = Activity(
            garmin_activity_id=garmin_id,

            garmin_uuid=summary.get("activityUUID"),

            name=name,
            sport_type=activity_type,

            start_date=parse_start_date(summary),

            distance_m=summary.get("distance"),

            moving_time_s=summary.get("movingDuration"),
            elapsed_time_s=summary.get("elapsedDuration"),
            duration_s=summary.get("duration"),

            elevation_gain_m=summary.get("elevationGain"),
            elevation_loss_m=summary.get("elevationLoss"),

            average_speed_mps=summary.get("averageSpeed"),
            max_speed_mps=summary.get("maxSpeed"),

            average_heartrate=summary.get("averageHR"),
            max_heartrate=summary.get("maxHR"),

            average_cadence_spm=summary.get(
                "averageRunningCadenceInStepsPerMinute"
            ),

            average_power_w=summary.get("avgPower"),
            max_power_w=summary.get("maxPower"),
            normalized_power_w=summary.get("normPower"),

            training_load=summary.get("activityTrainingLoad"),

            aerobic_training_effect=summary.get(
                "aerobicTrainingEffect"
            ),

            anaerobic_training_effect=summary.get(
                "anaerobicTrainingEffect"
            ),

            vo2max=summary.get("vO2MaxValue"),

            calories=summary.get("calories"),

            fit_file_path=str(fit_path),

            raw_summary_json=summary,

            synced_at=datetime.now(timezone.utc),
        )

        db.add(activity)
        db.flush()

        messages = decode_fit(str(fit_path))

        laps = build_laps(
            activity.id,
            messages,
        )

        records = build_records(
            activity.id,
            messages,
        )

        db.add_all(laps)
        db.add_all(records)

        db.commit()

        print(
            f"[OK] {garmin_id}: "
            f"{len(laps)} laps, "
            f"{len(records)} records"
        )

        return True

    except Exception:

        db.rollback()
        raise

    finally:

        db.close()


def get_history(api, max_activities=None):

    offset = 0
    processed = 0
    new_activities = 0

    while True:

        limit = PAGE_SIZE

        if max_activities is not None:
            remaining = max_activities - processed

            if remaining <= 0:
                break

            limit = min(limit, remaining)

        activities = garmin_call(
            api.get_activities,
            offset,
            limit,
        )

        if not activities:
            break

        for activity in activities:

            if sync_activity(
                api,
                activity,
            ):
                new_activities += 1

            processed += 1

            # On reste gentil avec Garmin.
            time.sleep(1)

        offset += len(activities)

        if len(activities) < limit:
            break

    print(
        f"\nTerminé : {processed} activités examinées, "
        f"{new_activities} nouvelles."
    )

    return new_activities


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Nombre max d'activités examinées",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Importer tout l'historique",
    )

    args = parser.parse_args()

    print("Connexion Garmin via token...")

    api = Garmin()
    api.login(TOKENSTORE)

    print(
        f"Garmin connecté : {api.get_full_name()}"
    )

    if args.all:

        count = garmin_call(
            api.count_activities
        )

        print(
            f"{count} activités Garmin trouvées."
        )

        new_activities = get_history(
            api,
            max_activities=None,
        )

    else:

        new_activities = get_history(
            api,
            max_activities=args.limit,
        )

    if new_activities:
        print("\nNouvelles activités détectées : génération du rapport Excel...")

        try:
            from app.services.generate_excel import main as generate_excel

            generate_excel()

        except Exception as exc:
            print(
                "[WARN] Les activités sont synchronisées, "
                f"mais le rapport Excel n'a pas pu être généré : {exc}"
            )


if __name__ == "__main__":
    main()

from garmin_fit_sdk import Decoder, Stream

from app.models.activity_lap import ActivityLap
from app.models.activity_record import ActivityRecord


def decode_fit(path: str):
    stream = Stream.from_file(path)
    decoder = Decoder(stream)

    messages, errors = decoder.read()

    if errors:
        print(f"FIT warnings: {errors}")

    return messages


def build_laps(activity_db_id: int, messages: dict):

    result = []

    for index, lap in enumerate(messages.get("lap_mesgs", [])):

        cadence = lap.get("avg_cadence")
        fractional = lap.get("avg_fractional_cadence", 0) or 0

        # FIT running cadence = cycles/min.
        # On convertit en steps/min.
        cadence_spm = None

        if cadence is not None:
            cadence_spm = (cadence + fractional) * 2

        result.append(
            ActivityLap(
                activity_id=activity_db_id,
                lap_index=index,

                start_time=lap.get("start_time"),

                total_distance_m=lap.get("total_distance"),
                total_timer_time_s=lap.get("total_timer_time"),
                total_elapsed_time_s=lap.get("total_elapsed_time"),

                total_ascent_m=lap.get("total_ascent"),
                total_descent_m=lap.get("total_descent"),

                avg_heart_rate=lap.get("avg_heart_rate"),
                max_heart_rate=lap.get("max_heart_rate"),

                avg_cadence=cadence_spm,

                max_cadence=(
                    lap.get("max_cadence") * 2
                    if lap.get("max_cadence") is not None
                    else None
                ),

                avg_power=lap.get("avg_power"),
                max_power=lap.get("max_power"),
                normalized_power=lap.get("normalized_power"),

                avg_speed_mps=lap.get("enhanced_avg_speed"),
                max_speed_mps=lap.get("enhanced_max_speed"),

                avg_stance_time_ms=lap.get("avg_stance_time"),
                avg_step_length_mm=lap.get("avg_step_length"),

                avg_vertical_oscillation_mm=lap.get(
                    "avg_vertical_oscillation"
                ),
                avg_vertical_ratio_pct=lap.get(
                    "avg_vertical_ratio"
                ),

                total_calories=lap.get("total_calories"),
            )
        )

    return result


def build_records(activity_db_id: int, messages: dict):

    result = []

    for index, record in enumerate(messages.get("record_mesgs", [])):

        cadence = record.get("cadence")
        fractional = record.get("fractional_cadence", 0) or 0

        cadence_spm = None

        if cadence is not None:
            cadence_spm = (cadence + fractional) * 2

        result.append(
            ActivityRecord(
                activity_id=activity_db_id,
                record_index=index,

                timestamp=record.get("timestamp"),

                distance_m=record.get("distance"),

                latitude_semicircles=record.get("position_lat"),
                longitude_semicircles=record.get("position_long"),

                altitude_m=record.get("enhanced_altitude"),
                speed_mps=record.get("enhanced_speed"),

                heart_rate_bpm=record.get("heart_rate"),
                cadence=cadence_spm,

                power_w=record.get("power"),
                accumulated_power=record.get("accumulated_power"),

                stance_time_ms=record.get("stance_time"),
                step_length_mm=record.get("step_length"),

                vertical_oscillation_mm=record.get(
                    "vertical_oscillation"
                ),
                vertical_ratio_pct=record.get(
                    "vertical_ratio"
                ),
            )
        )

    return result

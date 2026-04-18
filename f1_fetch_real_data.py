import argparse
import csv
import json
import os
import statistics

from f1_data import REFERENCE_DIR, TRACKS_DIR, TRACK_EVENT_ALIASES, ensure_data_dirs, slugify


def export_track_csv(path, telemetry):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["# X", "Y"])
        for x, y in zip(telemetry["X"], telemetry["Y"]):
            if x == x and y == y:
                writer.writerow([float(x) / 10.0, float(y) / 10.0])


def is_green_lap(row):
    status = str(row.get("TrackStatus", "") or "").strip()
    return not status or all(ch == "1" for ch in status if ch.isdigit())


def clean_reference_laps(laps, session_name):
    clean = laps.dropna(subset=["LapTime"]).copy()
    if "PitOutTime" in clean:
        clean = clean[clean["PitOutTime"].isna()]
    if "PitInTime" in clean:
        clean = clean[clean["PitInTime"].isna()]
    if "TrackStatus" in clean:
        clean = clean[clean.apply(is_green_lap, axis=1)]
    if clean.empty:
        clean = laps.dropna(subset=["LapTime"]).copy()
    session_key = str(session_name).upper()
    if session_key in ("R", "S"):
        return clean.sort_values("LapTime")
    return clean.sort_values("LapTime")


def pick_reference_lap(clean_laps, session_name):
    if clean_laps.empty:
        raise SystemExit("No se encontraron vueltas limpias para construir la referencia.")
    session_key = str(session_name).upper()
    if session_key in ("R", "S"):
        median_time = clean_laps["LapTime"].median()
        ranked = clean_laps.assign(
            _delta=clean_laps["LapTime"].apply(lambda x: abs((x - median_time).total_seconds()))
        ).sort_values("_delta")
        return ranked.iloc[0]
    return clean_laps.iloc[0]


def pick_telemetry_lap(candidate_laps):
    for _, lap in candidate_laps.iterrows():
        try:
            telemetry = lap.get_telemetry().add_distance()
        except Exception:
            continue
        if {"X", "Y"}.issubset(set(telemetry.columns)) and telemetry[["X", "Y"]].dropna().shape[0] > 50:
            return lap, telemetry
    raise SystemExit("No se pudo obtener una telemetria valida del circuito para esta sesion.")


def build_team_snapshot(session, candidate_laps, session_name):
    teams = {}
    session_key = str(session_name).upper()
    grouped = candidate_laps.groupby("Team", dropna=True)
    for team, team_laps in grouped:
        team_laps = team_laps.dropna(subset=["LapTime"]).sort_values("LapTime").copy()
        if team_laps.empty:
            continue
        if session_key in ("R", "S"):
            median_time = team_laps["LapTime"].median()
            lap = team_laps.assign(
                _delta=team_laps["LapTime"].apply(lambda x: abs((x - median_time).total_seconds()))
            ).sort_values("_delta").iloc[0]
        else:
            lap = team_laps.iloc[0]
        telemetry = lap.get_car_data().add_distance()
        speed = telemetry["Speed"].dropna()
        throttle = telemetry["Throttle"].dropna() if "Throttle" in telemetry else []
        brake = telemetry["Brake"].dropna() if "Brake" in telemetry else []
        teams[str(team)] = {
            "driver": str(lap["Driver"]),
            "lap_time_s": float(lap["LapTime"].total_seconds()),
            "avg_speed_kph": float(speed.mean()) if len(speed) else None,
            "top_speed_kph": float(speed.max()) if len(speed) else None,
            "speed_p25_kph": float(speed.quantile(0.25)) if len(speed) else None,
            "speed_p75_kph": float(speed.quantile(0.75)) if len(speed) else None,
            "full_throttle_ratio": float((throttle > 98).mean()) if len(throttle) else None,
            "brake_ratio": float(brake.astype(int).mean()) if len(brake) else None,
        }
    return teams


def build_reference(year, event, session_name, cache_dir, output_name=None):
    try:
        import fastf1
    except ImportError as exc:
        raise SystemExit(
            "FastF1 no esta instalado. Instala dependencias con: pip install fastf1 pandas numpy"
        ) from exc

    ensure_data_dirs()
    os.makedirs(cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(cache_dir)
    session = fastf1.get_session(year, event, session_name)
    session.load(laps=True, telemetry=True, weather=True, messages=False)

    laps = session.laps.pick_accurate()
    candidate_laps = clean_reference_laps(laps, session_name)
    if candidate_laps.empty:
        raise SystemExit("No se encontraron vueltas validas para construir la referencia.")

    reference_lap = pick_reference_lap(candidate_laps, session_name)
    _, telemetry = pick_telemetry_lap(candidate_laps)
    circuit_info = session.get_circuit_info()
    weather = reference_lap.get_weather_data()
    track_label = output_name or event
    track_slug = slugify(track_label)

    reference = {
        "source": "FastF1",
        "year": int(year),
        "event": str(session.event["EventName"]),
        "requested_event": str(event),
        "track_name": str(track_label),
        "session": str(session_name),
        "track": {
            "turn_count": int(len(circuit_info.corners)) if circuit_info and circuit_info.corners is not None else None,
            "lap_length_m": float(telemetry["Distance"].max()) if "Distance" in telemetry else None,
            "fuel_per_lap_kg": None,
            "pit_loss_s": None,
            "rotation_deg": float(circuit_info.rotation) if circuit_info else None,
        },
        "weather": {
            "air_temp_c": float(weather["AirTemp"]) if "AirTemp" in weather else None,
            "track_temp_c": float(weather["TrackTemp"]) if "TrackTemp" in weather else None,
            "humidity_pct": float(weather["Humidity"]) if "Humidity" in weather else None,
            "wind_speed_ms": float(weather["WindSpeed"]) if "WindSpeed" in weather else None,
            "rainfall": bool(weather["Rainfall"]) if "Rainfall" in weather else None,
        },
        "reference_lap_time_s": float(reference_lap["LapTime"].total_seconds()),
        "reference_driver": str(reference_lap["Driver"]),
        "reference_mode": "median_clean_lap" if str(session_name).upper() in ("R", "S") else "fastest_lap",
        "teams": build_team_snapshot(session, candidate_laps, session_name),
    }

    if "FuelInTank" in candidate_laps.columns:
        fuel_series = candidate_laps["FuelInTank"].dropna()
        if len(fuel_series) >= 2:
            deltas = [fuel_series.iloc[i] - fuel_series.iloc[i + 1] for i in range(len(fuel_series) - 1)]
            deltas = [d for d in deltas if d > 0]
            if deltas:
                reference["track"]["fuel_per_lap_kg"] = float(statistics.mean(deltas))

    pit_rows = laps[laps["PitOutTime"].notna() | laps["PitInTime"].notna()]
    if len(pit_rows) >= 2:
        pit_deltas = []
        for _, row in pit_rows.iterrows():
            lap_time = row["LapTime"]
            stint_laps = laps[(laps["Driver"] == row["Driver"]) & laps["LapTime"].notna()]
            if lap_time is not None and not stint_laps.empty:
                baseline = stint_laps["LapTime"].median().total_seconds()
                pit_deltas.append(max(0.0, lap_time.total_seconds() - baseline))
        if pit_deltas:
            reference["track"]["pit_loss_s"] = float(statistics.median(pit_deltas))

    csv_path = os.path.join(TRACKS_DIR, f"{track_slug}.csv")
    export_track_csv(csv_path, telemetry)

    json_path = os.path.join(REFERENCE_DIR, f"{track_slug}_{year}_{slugify(session_name)}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(reference, f, indent=2)

    return csv_path, json_path


def main():
    parser = argparse.ArgumentParser(description="Descarga y guarda datos reales de F1 para el simulador.")
    parser.add_argument("--year", type=int, required=True, help="Ano de la sesion, por ejemplo 2025")
    parser.add_argument("--event", required=True, help="Nombre del GP segun FastF1, por ejemplo Monza o Japan")
    parser.add_argument("--session", default="Q", help="Sesion: Q, R, FP1, FP2, FP3, SQ o S")
    parser.add_argument("--cache-dir", default=os.path.join(os.path.dirname(__file__), ".fastf1_cache"))
    parser.add_argument("--output-name", default=None, help="Nombre canonico del circuito para guardar CSV/JSON")
    args = parser.parse_args()

    output_name = args.output_name
    if not output_name:
        for track_name, aliases in TRACK_EVENT_ALIASES.items():
            if slugify(args.event) in {slugify(track_name), *(slugify(alias) for alias in aliases)}:
                output_name = track_name
                break
    csv_path, json_path = build_reference(args.year, args.event, args.session, args.cache_dir, output_name=output_name)
    print("Track CSV:", csv_path)
    print("Reference JSON:", json_path)


if __name__ == "__main__":
    main()

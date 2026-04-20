import csv
import json
import math
import os
import re
import unicodedata
from typing import Dict, List, Optional


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TRACKS_DIR = os.path.join(DATA_DIR, "tracks")
REFERENCE_DIR = os.path.join(DATA_DIR, "reference")


def ensure_data_dirs() -> None:
    os.makedirs(TRACKS_DIR, exist_ok=True)
    os.makedirs(REFERENCE_DIR, exist_ok=True)


def slugify(value: str) -> str:
    clean = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    clean = re.sub(r"[^a-z0-9]+", "_", clean)
    return clean.strip("_")


# Circuit lengths and lap counts are aligned with official Formula1.com circuit pages.
TRACKS: Dict[str, dict] = {
    "Bahrain": {
        "lapDistanceKm": 5.412,
        "raceLaps": 57,
        "turns": 15,
        "drsZones": 3,
        "pitLoss": 22.1,
        "fuelPerLapKg": 1.92,
        "tyreStress": 1.03,
        "brakeStress": 0.84,
        "segments": [
            dict(type="straight", distanceKm=1.12),
            dict(type="slow", distanceKm=0.71),
            dict(type="straight", distanceKm=0.88),
            dict(type="fast", distanceKm=1.09),
            dict(type="slow", distanceKm=0.72),
            dict(type="straight", distanceKm=0.892),
        ],
    },
    "Jeddah": {
        "lapDistanceKm": 6.174,
        "raceLaps": 50,
        "turns": 27,
        "drsZones": 3,
        "pitLoss": 20.6,
        "fuelPerLapKg": 2.05,
        "tyreStress": 0.92,
        "brakeStress": 0.66,
        "segments": [
            dict(type="straight", distanceKm=1.21),
            dict(type="fast", distanceKm=1.74),
            dict(type="straight", distanceKm=0.97),
            dict(type="fast", distanceKm=1.47),
            dict(type="slow", distanceKm=0.78),
        ],
    },
    "Melbourne": {
        "lapDistanceKm": 5.278,
        "raceLaps": 58,
        "turns": 14,
        "drsZones": 4,
        "pitLoss": 20.1,
        "fuelPerLapKg": 1.82,
        "tyreStress": 0.98,
        "brakeStress": 0.86,
        "segments": [
            dict(type="straight", distanceKm=1.04),
            dict(type="fast", distanceKm=1.21),
            dict(type="straight", distanceKm=0.82),
            dict(type="slow", distanceKm=0.66),
            dict(type="fast", distanceKm=1.548),
        ],
    },
    "Barcelona": {
        "lapDistanceKm": 4.657,
        "raceLaps": 66,
        "turns": 14,
        "drsZones": 2,
        "pitLoss": 21.0,
        "fuelPerLapKg": 1.74,
        "tyreStress": 1.02,
        "brakeStress": 0.82,
        "segments": [
            dict(type="straight", distanceKm=0.97),
            dict(type="fast", distanceKm=1.24),
            dict(type="slow", distanceKm=0.63),
            dict(type="fast", distanceKm=1.12),
            dict(type="slow", distanceKm=0.697),
        ],
    },
    "Montreal": {
        "lapDistanceKm": 4.361,
        "raceLaps": 70,
        "turns": 14,
        "drsZones": 3,
        "pitLoss": 20.9,
        "fuelPerLapKg": 1.60,
        "tyreStress": 0.93,
        "brakeStress": 0.90,
        "segments": [
            dict(type="straight", distanceKm=1.01),
            dict(type="slow", distanceKm=0.59),
            dict(type="straight", distanceKm=0.84),
            dict(type="fast", distanceKm=0.88),
            dict(type="slow", distanceKm=0.58),
            dict(type="straight", distanceKm=0.461),
        ],
    },
    "Spielberg": {
        "lapDistanceKm": 4.318,
        "raceLaps": 71,
        "turns": 10,
        "drsZones": 3,
        "pitLoss": 19.4,
        "fuelPerLapKg": 1.58,
        "tyreStress": 0.95,
        "brakeStress": 0.91,
        "segments": [
            dict(type="straight", distanceKm=1.06),
            dict(type="slow", distanceKm=0.56),
            dict(type="straight", distanceKm=0.73),
            dict(type="fast", distanceKm=0.95),
            dict(type="slow", distanceKm=0.44),
            dict(type="straight", distanceKm=0.578),
        ],
    },
    "Monza": {
        "lapDistanceKm": 5.793,
        "raceLaps": 53,
        "turns": 11,
        "drsZones": 2,
        "pitLoss": 22.5,
        "fuelPerLapKg": 1.72,
        "tyreStress": 0.90,
        "brakeStress": 0.93,
        "segments": [
            dict(type="straight", distanceKm=1.18),
            dict(type="slow", distanceKm=0.52),
            dict(type="straight", distanceKm=0.95),
            dict(type="fast", distanceKm=0.74),
            dict(type="straight", distanceKm=1.08),
            dict(type="slow", distanceKm=0.45),
            dict(type="fast", distanceKm=0.88),
        ],
    },
    "Silverstone": {
        "lapDistanceKm": 5.891,
        "raceLaps": 52,
        "turns": 18,
        "drsZones": 2,
        "pitLoss": 20.8,
        "fuelPerLapKg": 1.86,
        "tyreStress": 1.12,
        "brakeStress": 0.77,
        "segments": [
            dict(type="straight", distanceKm=0.96),
            dict(type="fast", distanceKm=1.42),
            dict(type="straight", distanceKm=0.91),
            dict(type="slow", distanceKm=0.63),
            dict(type="fast", distanceKm=1.97),
        ],
    },
    "Spa-Francorchamps": {
        "lapDistanceKm": 7.004,
        "raceLaps": 44,
        "turns": 19,
        "drsZones": 2,
        "pitLoss": 23.5,
        "fuelPerLapKg": 2.18,
        "tyreStress": 0.97,
        "brakeStress": 0.71,
        "segments": [
            dict(type="slow", distanceKm=0.42),
            dict(type="straight", distanceKm=1.32),
            dict(type="fast", distanceKm=1.44),
            dict(type="straight", distanceKm=1.18),
            dict(type="fast", distanceKm=1.26),
            dict(type="straight", distanceKm=0.78),
            dict(type="slow", distanceKm=0.62),
        ],
    },
    "Interlagos": {
        "lapDistanceKm": 4.309,
        "raceLaps": 71,
        "turns": 15,
        "drsZones": 2,
        "pitLoss": 21.4,
        "fuelPerLapKg": 1.54,
        "tyreStress": 1.04,
        "brakeStress": 0.88,
        "segments": [
            dict(type="straight", distanceKm=0.84),
            dict(type="slow", distanceKm=0.71),
            dict(type="fast", distanceKm=1.02),
            dict(type="slow", distanceKm=0.54),
            dict(type="straight", distanceKm=1.239),
        ],
    },
    "Suzuka": {
        "lapDistanceKm": 5.807,
        "raceLaps": 53,
        "turns": 18,
        "drsZones": 1,
        "pitLoss": 21.9,
        "fuelPerLapKg": 1.80,
        "tyreStress": 1.15,
        "brakeStress": 0.79,
        "segments": [
            dict(type="fast", distanceKm=1.42),
            dict(type="slow", distanceKm=0.68),
            dict(type="straight", distanceKm=0.88),
            dict(type="fast", distanceKm=1.52),
            dict(type="slow", distanceKm=0.49),
            dict(type="straight", distanceKm=0.817),
        ],
    },
    "Monaco": {
        "lapDistanceKm": 3.337,
        "raceLaps": 78,
        "turns": 19,
        "drsZones": 1,
        "pitLoss": 19.8,
        "fuelPerLapKg": 1.36,
        "tyreStress": 0.86,
        "brakeStress": 0.72,
        "segments": [
            dict(type="slow", distanceKm=0.74),
            dict(type="fast", distanceKm=0.61),
            dict(type="slow", distanceKm=0.52),
            dict(type="straight", distanceKm=0.47),
            dict(type="slow", distanceKm=0.48),
            dict(type="fast", distanceKm=0.517),
        ],
    },
    "Singapore": {
        "lapDistanceKm": 4.940,
        "raceLaps": 62,
        "turns": 19,
        "drsZones": 3,
        "pitLoss": 27.0,
        "fuelPerLapKg": 2.35,
        "tyreStress": 1.18,
        "brakeStress": 0.83,
        "segments": [
            dict(type="slow", distanceKm=0.81),
            dict(type="straight", distanceKm=0.67),
            dict(type="slow", distanceKm=0.74),
            dict(type="fast", distanceKm=0.95),
            dict(type="slow", distanceKm=0.72),
            dict(type="straight", distanceKm=1.05),
        ],
    },
    "Abu Dhabi": {
        "lapDistanceKm": 5.281,
        "raceLaps": 58,
        "turns": 16,
        "drsZones": 2,
        "pitLoss": 21.6,
        "fuelPerLapKg": 1.84,
        "tyreStress": 0.98,
        "brakeStress": 0.80,
        "segments": [
            dict(type="straight", distanceKm=1.17),
            dict(type="slow", distanceKm=0.69),
            dict(type="straight", distanceKm=0.94),
            dict(type="fast", distanceKm=1.26),
            dict(type="slow", distanceKm=0.58),
            dict(type="straight", distanceKm=0.641),
        ],
    },
}


TRACK_EVENT_ALIASES: Dict[str, List[str]] = {
    "Bahrain": ["Bahrain", "Sakhir", "Bahrain Grand Prix"],
    "Jeddah": ["Jeddah", "Saudi Arabia", "Saudi Arabian Grand Prix"],
    "Melbourne": ["Melbourne", "Australia", "Australian Grand Prix"],
    "Barcelona": ["Barcelona", "Spain", "Spanish Grand Prix", "Catalunya"],
    "Montreal": ["Montreal", "Canada", "Canadian Grand Prix"],
    "Spielberg": ["Spielberg", "Austria", "Austrian Grand Prix", "Red Bull Ring"],
    "Monza": ["Monza", "Italy", "Italian Grand Prix"],
    "Silverstone": ["Silverstone", "Great Britain", "British Grand Prix"],
    "Spa-Francorchamps": ["Spa", "Spa-Francorchamps", "Belgium", "Belgian Grand Prix"],
    "Interlagos": ["Interlagos", "Brazil", "Sao Paulo", "Sao Paulo Grand Prix", "Brazilian Grand Prix"],
    "Suzuka": ["Suzuka", "Japan", "Japanese Grand Prix"],
    "Monaco": ["Monaco", "Monaco Grand Prix"],
    "Singapore": ["Singapore", "Singapore Grand Prix", "Marina Bay"],
    "Abu Dhabi": ["Abu Dhabi", "UAE", "United Arab Emirates", "Abu Dhabi Grand Prix", "Yas Marina"],
}


# Official 2026 teams from Formula1.com teams page.
# Exact car specs are not public, so these are calibrated performance profiles.
TEAMS: Dict[str, dict] = {
    "McLaren": dict(power=767, mass=770, drag=0.84, downforce=1.17, traction=1.17, brake=1.15, ers=1.00),
    "Mercedes": dict(power=766, mass=770, drag=0.84, downforce=1.16, traction=1.16, brake=1.15, ers=0.99),
    "Ferrari": dict(power=765, mass=770, drag=0.85, downforce=1.16, traction=1.15, brake=1.14, ers=0.99),
    "Red Bull Racing": dict(power=764, mass=769, drag=0.83, downforce=1.15, traction=1.16, brake=1.13, ers=0.99),
    "Williams": dict(power=760, mass=771, drag=0.86, downforce=1.13, traction=1.12, brake=1.11, ers=0.97),
    "Aston Martin": dict(power=759, mass=771, drag=0.86, downforce=1.12, traction=1.11, brake=1.10, ers=0.97),
    "Alpine": dict(power=758, mass=772, drag=0.87, downforce=1.12, traction=1.10, brake=1.09, ers=0.96),
    "Haas F1 Team": dict(power=758, mass=772, drag=0.87, downforce=1.11, traction=1.10, brake=1.09, ers=0.96),
    "Racing Bulls": dict(power=757, mass=771, drag=0.86, downforce=1.12, traction=1.11, brake=1.10, ers=0.96),
    "Audi": dict(power=756, mass=773, drag=0.88, downforce=1.10, traction=1.08, brake=1.08, ers=0.95),
    "Cadillac": dict(power=754, mass=774, drag=0.89, downforce=1.09, traction=1.07, brake=1.07, ers=0.95),
}


TIRES: Dict[str, dict] = {
    "C1 Hard": dict(grip=0.99, wear=0.74, warmup=0.92, wetGrip=0.45),
    "C2 Hard": dict(grip=1.01, wear=0.82, warmup=0.95, wetGrip=0.46),
    "C3 Medium": dict(grip=1.04, wear=0.94, warmup=0.99, wetGrip=0.47),
    "C4 Soft": dict(grip=1.07, wear=1.08, warmup=1.04, wetGrip=0.48),
    "C5 Soft": dict(grip=1.10, wear=1.22, warmup=1.08, wetGrip=0.49),
    "Intermedio": dict(grip=0.93, wear=0.98, warmup=1.02, wetGrip=0.88),
    "Lluvia extrema": dict(grip=0.87, wear=1.06, warmup=1.04, wetGrip=1.00),
}


WEATHER: Dict[str, dict] = {
    "dry": dict(gripFactor=1.00, dragFactor=1.00, degFactor=1.00, fuelFactor=1.00, topSpeedFactor=1.00),
    "hot": dict(gripFactor=0.985, dragFactor=0.995, degFactor=1.14, fuelFactor=1.01, topSpeedFactor=1.00),
    "cool": dict(gripFactor=1.01, dragFactor=1.005, degFactor=0.93, fuelFactor=0.995, topSpeedFactor=1.00),
    "damp": dict(gripFactor=0.92, dragFactor=1.02, degFactor=1.07, fuelFactor=1.02, topSpeedFactor=0.985),
    "wet": dict(gripFactor=0.80, dragFactor=1.07, degFactor=0.97, fuelFactor=1.05, topSpeedFactor=0.94),
}


def _candidate_track_dirs() -> List[str]:
    return [
        TRACKS_DIR,
        BASE_DIR,
        os.path.dirname(BASE_DIR),
    ]


def find_track_csv(track_name: str) -> Optional[str]:
    ensure_data_dirs()
    slug = slugify(track_name)
    candidates = []
    for root in _candidate_track_dirs():
        if not os.path.isdir(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                if not filename.lower().endswith(".csv"):
                    continue
                full = os.path.join(dirpath, filename)
                name_slug = slugify(os.path.splitext(filename)[0])
                if slug in name_slug or name_slug in slug:
                    candidates.append(full)
    for path in sorted(candidates, key=lambda p: (0 if os.path.dirname(p) == TRACKS_DIR else 1, len(p))):
        return path
    return None


def load_track_points(track_name: str) -> Optional[List[dict]]:
    path = find_track_csv(track_name)
    if not path:
        return None
    points = []
    with open(path, encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or row[0].startswith("#"):
                continue
            try:
                x = float(row[0])
                y = float(row[1])
                if math.isfinite(x) and math.isfinite(y):
                    points.append(dict(x=x, y=y))
            except (TypeError, ValueError):
                continue
    return points if len(points) > 50 else None


def _angle_wrap(angle: float) -> float:
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


def build_track_from_points(track_name: str) -> Optional[dict]:
    points = load_track_points(track_name)
    if not points:
        return None
    sanitized = [points[0]]
    for point in points[1:]:
        if math.hypot(point["x"] - sanitized[-1]["x"], point["y"] - sanitized[-1]["y"]) >= 1e-4:
            sanitized.append(point)
    points = sanitized
    if len(points) < 8:
        return None
    loop = points + [dict(points[0])]
    distances = []
    total_m = 0.0
    for i in range(1, len(loop)):
        dist = math.hypot(loop[i]["x"] - loop[i - 1]["x"], loop[i]["y"] - loop[i - 1]["y"])
        distances.append(dist)
        total_m += dist
    curvature = [0.0] * len(loop)
    for i in range(1, len(loop) - 1):
        a1 = math.atan2(loop[i]["y"] - loop[i - 1]["y"], loop[i]["x"] - loop[i - 1]["x"])
        a2 = math.atan2(loop[i + 1]["y"] - loop[i]["y"], loop[i + 1]["x"] - loop[i]["x"])
        avg_ds = max(
            0.6,
            (
                math.hypot(loop[i]["x"] - loop[i - 1]["x"], loop[i]["y"] - loop[i - 1]["y"])
                + math.hypot(loop[i + 1]["x"] - loop[i]["x"], loop[i + 1]["y"] - loop[i]["y"])
            ) * 0.5,
        )
        curvature[i] = abs(_angle_wrap(a2 - a1)) / avg_ds
    curvature[0], curvature[-1] = curvature[-2], curvature[1]
    smooth = [sum(curvature[(i + k) % len(curvature)] for k in range(-4, 5)) / 9.0 for i in range(len(curvature))]
    types = [
        "straight" if smooth[i] < 0.00175 else "fast" if smooth[i] < 0.0055 else "slow"
        for i in range(len(distances))
    ]
    merged = []
    for i, seg_type in enumerate(types):
        if not merged or merged[-1]["type"] != seg_type:
            merged.append(dict(type=seg_type, distanceM=distances[i]))
        else:
            merged[-1]["distanceM"] += distances[i]
    i = 1
    while i < len(merged) - 1:
        if merged[i]["distanceM"] < 70:
            merged[i - 1]["distanceM"] += merged[i]["distanceM"]
            merged.pop(i)
            i -= 1
        i += 1
    track = TRACKS[track_name]
    scale = (track["lapDistanceKm"] * 1000.0) / max(total_m, 1e-6)
    return dict(
        pointsMeters=points,
        lapDistanceKm=track["lapDistanceKm"],
        raceLaps=track["raceLaps"],
        turns=track["turns"],
        drsZones=track["drsZones"],
        pitLoss=track["pitLoss"],
        fuelPerLapKg=track["fuelPerLapKg"],
        tyreStress=track["tyreStress"],
        brakeStress=track["brakeStress"],
        segments=[dict(type=s["type"], distanceKm=(s["distanceM"] * scale) / 1000.0) for s in merged],
    )


def iter_reference_profiles(track_name: str) -> List[dict]:
    ensure_data_dirs()
    slugs = [slugify(track_name)] + [slugify(alias) for alias in TRACK_EVENT_ALIASES.get(track_name, [])]
    refs: List[dict] = []
    if not os.path.isdir(REFERENCE_DIR):
        return refs
    for filename in sorted(os.listdir(REFERENCE_DIR), reverse=True):
        if not filename.endswith(".json"):
            continue
        if not any(filename.startswith(slug) for slug in slugs):
            continue
        path = os.path.join(REFERENCE_DIR, filename)
        try:
            with open(path, encoding="utf-8") as f:
                refs.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            continue
    return refs


def load_reference_profile(track_name: str, year: Optional[int] = None, session: Optional[str] = None) -> Optional[dict]:
    refs = iter_reference_profiles(track_name)
    if not refs:
        return None
    if year is not None and session is not None:
        session_key = str(session).upper()
        for ref in refs:
            if int(ref.get("year", 0)) == int(year) and str(ref.get("session", "")).upper() == session_key:
                return ref
    return refs[0]


def available_reference_sessions(track_name: str) -> List[str]:
    sessions = []
    for ref in iter_reference_profiles(track_name):
        year = ref.get("year", "?")
        session = ref.get("session", "?")
        label = f"{year} {session}"
        if label not in sessions:
            sessions.append(label)
    return sessions


def available_reference_years(track_name: str) -> List[str]:
    years = []
    for ref in iter_reference_profiles(track_name):
        year = str(ref.get("year", "?"))
        if year not in years:
            years.append(year)
    return years


def available_sessions_for_year(track_name: str, year: Optional[int] = None) -> List[str]:
    sessions = []
    for ref in iter_reference_profiles(track_name):
        ref_year = str(ref.get("year", "?"))
        if year is not None and ref_year != str(year):
            continue
        session = str(ref.get("session", "?")).upper()
        if session not in sessions:
            sessions.append(session)
    return sessions


def available_reference_tracks() -> List[str]:
    tracks = []
    for track_name in TRACKS:
        if iter_reference_profiles(track_name):
            tracks.append(track_name)
    return tracks

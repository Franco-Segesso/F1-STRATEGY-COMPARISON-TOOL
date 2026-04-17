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
}


TRACK_EVENT_ALIASES: Dict[str, List[str]] = {
    "Monza": ["Monza", "Italy", "Italian Grand Prix"],
    "Silverstone": ["Silverstone", "Great Britain", "British Grand Prix"],
    "Spa-Francorchamps": ["Spa", "Spa-Francorchamps", "Belgium", "Belgian Grand Prix"],
    "Interlagos": ["Interlagos", "Brazil", "Sao Paulo", "Sao Paulo Grand Prix", "Brazilian Grand Prix"],
    "Suzuka": ["Suzuka", "Japan", "Japanese Grand Prix"],
}


# Official 2026 teams from Formula1.com teams page.
# Exact car specs are not public, so these are calibrated performance profiles.
TEAMS: Dict[str, dict] = {
    "McLaren": dict(power=770, mass=768, drag=0.82, downforce=1.23, traction=1.20, brake=1.16, ers=1.00),
    "Mercedes": dict(power=772, mass=769, drag=0.83, downforce=1.22, traction=1.18, brake=1.17, ers=1.00),
    "Ferrari": dict(power=769, mass=769, drag=0.84, downforce=1.21, traction=1.17, brake=1.15, ers=0.99),
    "Red Bull Racing": dict(power=764, mass=768, drag=0.81, downforce=1.19, traction=1.18, brake=1.13, ers=0.98),
    "Haas F1 Team": dict(power=756, mass=771, drag=0.86, downforce=1.14, traction=1.12, brake=1.10, ers=0.97),
    "Alpine": dict(power=755, mass=771, drag=0.87, downforce=1.13, traction=1.10, brake=1.09, ers=0.96),
    "Racing Bulls": dict(power=754, mass=770, drag=0.85, downforce=1.12, traction=1.11, brake=1.09, ers=0.96),
    "Audi": dict(power=751, mass=772, drag=0.87, downforce=1.10, traction=1.09, brake=1.07, ers=0.95),
    "Williams": dict(power=752, mass=771, drag=0.86, downforce=1.09, traction=1.08, brake=1.07, ers=0.95),
    "Cadillac": dict(power=748, mass=773, drag=0.88, downforce=1.08, traction=1.06, brake=1.05, ers=0.94),
    "Aston Martin": dict(power=747, mass=772, drag=0.88, downforce=1.07, traction=1.05, brake=1.05, ers=0.94),
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
                points.append(dict(x=float(row[0]), y=float(row[1])))
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


def load_reference_profile(track_name: str) -> Optional[dict]:
    ensure_data_dirs()
    slugs = [slugify(track_name)] + [slugify(alias) for alias in TRACK_EVENT_ALIASES.get(track_name, [])]
    if not os.path.isdir(REFERENCE_DIR):
        return None
    for filename in sorted(os.listdir(REFERENCE_DIR), reverse=True):
        if not filename.endswith(".json"):
            continue
        if not any(filename.startswith(slug) for slug in slugs):
            continue
        path = os.path.join(REFERENCE_DIR, filename)
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None
    return None

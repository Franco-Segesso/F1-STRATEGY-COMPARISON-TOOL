import math
import os

from f1_data import TEAMS, TIRES, TRACKS, WEATHER, build_track_from_points, load_reference_profile


G, RHO = 9.81, 1.225
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".fastf1_cache")


def clamp(x, a, b):
    return max(a, min(b, x))


def fmt_sec(s):
    m = int(s // 60)
    return f"{m}:{(s - m * 60):06.3f}"


def pit_sched(total, stops):
    if stops <= 0:
        return []
    return [max(2, min(total - 1, round(i * total / (stops + 1)))) for i in range(1, stops + 1)]


REAL_TRACKS = {name: build_track_from_points(name) for name in TRACKS}


def refresh_real_track(track_name):
    REAL_TRACKS[track_name] = build_track_from_points(track_name)
    return REAL_TRACKS[track_name]


def track_layout(name):
    real = REAL_TRACKS.get(name)
    return real if real else TRACKS[name]


def reference_adjustments(track_name, team_name):
    ref = load_reference_profile(track_name)
    if not ref:
        return {}
    team_data = (ref.get("teams") or {}).get(team_name, {})
    track_data = ref.get("track", {})
    return dict(
        topSpeedKph=team_data.get("top_speed_kph"),
        avgLapKph=team_data.get("avg_speed_kph"),
        fuelPerLapKg=track_data.get("fuel_per_lap_kg"),
        pitLoss=track_data.get("pit_loss_s"),
    )


def normalize_tire_plan(cfg):
    stops = max(0, int(cfg.get("stops", 0)))
    plan = [cfg["tireName"]]
    for idx in range(1, stops + 1):
        key = f"pitTire{idx}"
        plan.append(cfg.get(key) or plan[-1])
    return plan


def integrate(params, seg, state, track):
    dist, dt = seg["distanceKm"] * 1000, 0.05
    base_radius = {"straight": 12000, "fast": 170, "slow": 72}[seg["type"]]
    x, v, t = 0, max(22, state["vEntry"]), 0
    top_speed = params["topSpeedMS"] * (0.985 if seg["type"] == "straight" else 0.88 if seg["type"] == "fast" else 0.72)
    while x < dist:
        m = params["mass"] + state["fuel"]
        tyre_state = max(0.72, 1 - 0.0031 * state["wear"])
        grip = max(0.78, params["gripEff"] * tyre_state)
        aero_downforce = 0.5 * RHO * params["downforce"] * v * v
        normal = m * G + aero_downforce
        traction = params["traction"] * grip * normal
        straight_drag_scale = 0.92 if seg["type"] == "straight" and track["drsZones"] > 0 else 1.0
        drag = 0.5 * RHO * params["dragEff"] * straight_drag_scale * v * v
        power_force = min((params["powerW"] + params["ersW"]) / max(v, 14), traction)
        rolling = 0.014 * m * G
        accel = (power_force - drag - rolling) / m
        if seg["type"] != "straight":
            vc = min(top_speed, math.sqrt(max(25, grip * G * base_radius)) * params["cornerFactor"])
            if v > vc:
                brake = (params["brakeMS2"] + 0.0045 * aero_downforce / m) * (1.05 if seg["type"] == "slow" else 0.92)
                accel = -max(0.5, brake * (v - vc) / max(v, 1))
        else:
            accel = min(accel, (params["topSpeedMS"] - v) / max(dt, 1e-6))
        v = max(14, min(params["topSpeedMS"], v + accel * dt))
        x += v * dt
        t += dt
        if t > 220:
            break
    return dict(t=t, vOut=v)


def simulate(cfg):
    w, track = WEATHER[cfg["weather"]], track_layout(cfg["trackName"])
    ref = reference_adjustments(cfg["trackName"], cfg["teamName"])
    top_speed_kph = ref.get("topSpeedKph") or cfg["topSpeedKph"]
    fuel_base = (ref.get("fuelPerLapKg") or track["fuelPerLapKg"]) * w["fuelFactor"]
    pit_loss = ref.get("pitLoss") or track["pitLoss"]
    tire_plan = normalize_tire_plan(cfg)
    current_tire_index = 0
    tire_name = tire_plan[current_tire_index]
    tire = TIRES[tire_name]
    p = dict(
        powerW=cfg["power"] * 1000,
        ersW=cfg["ers"] * 120000,
        mass=cfg["mass"],
        dragEff=cfg["drag"] * w["dragFactor"],
        downforce=cfg["downforce"] * 1.55,
        traction=cfg["traction"],
        brakeMS2=cfg["brake"] * 11.8 * track["brakeStress"],
        gripEff=tire["grip"] * w["gripFactor"] * tire["warmup"],
        cornerFactor=1.0 + 0.06 * (cfg["downforce"] - 1.0),
        topSpeedMS=(top_speed_kph * w["topSpeedFactor"]) / 3.6,
    )
    pits = pit_sched(cfg["laps"], cfg["stops"])
    st = dict(fuel=cfg["fuel"], wear=0, vEntry=62)
    laps = []
    finished = True
    retired_lap = None
    for lap in range(1, cfg["laps"] + 1):
        if st["fuel"] <= 0.05:
            finished = False
            retired_lap = lap
            break
        ld = dict(
            lap=lap,
            segV=dict(straight=0, fast=0, slow=0),
            segStats={k: dict(d=0, t=0) for k in ("straight", "fast", "slow")},
            pit=False,
            tire=tire_name,
        )
        lap_t = 0
        vc = st["vEntry"]
        for seg in track["segments"]:
            r = integrate(p, seg, dict(fuel=st["fuel"], wear=st["wear"], vEntry=vc), track)
            lap_t += r["t"]
            vc = r["vOut"] * (0.70 if seg["type"] == "slow" else 0.84 if seg["type"] == "fast" else 0.90)
            ld["segStats"][seg["type"]]["d"] += seg["distanceKm"] * 1000
            ld["segStats"][seg["type"]]["t"] += r["t"]
        for k, ss in ld["segStats"].items():
            ld["segV"][k] = (ss["d"] / ss["t"]) * 3.6 if ss["t"] > 0 else 0
        wear_gain = tire["wear"] * cfg["degrade"] * w["degFactor"] * track["tyreStress"] * (0.78 + 0.0048 * st["fuel"])
        if cfg["weather"] == "wet" and cfg["tireName"] not in ("Intermedio", "Lluvia extrema"):
            wear_gain *= 1.15
        st["wear"] += wear_gain
        st["fuel"] = max(0, st["fuel"] - (fuel_base * (0.985 + 0.00032 * lap_t)))
        if lap in pits:
            lap_t += pit_loss
            st["wear"] = max(6, st["wear"] * 0.18)
            ld["pit"] = True
            current_tire_index = min(current_tire_index + 1, len(tire_plan) - 1)
            tire_name = tire_plan[current_tire_index]
            tire = TIRES[tire_name]
            p["gripEff"] = tire["grip"] * w["gripFactor"] * tire["warmup"]
        ld["time"], ld["wear"], ld["fuel"] = lap_t, st["wear"], st["fuel"]
        laps.append(ld)
        st["vEntry"] = max(45, vc)
    avg = {k: (sum(l["segV"][k] for l in laps) / len(laps) if laps else 0) for k in ("straight", "fast", "slow")}
    total = sum(l["time"] for l in laps)
    best = min((l["time"] for l in laps), default=float("inf"))
    return dict(
        laps=laps,
        total=total,
        best=best,
        avgSegment=avg,
        pitLaps=pits,
        tirePlan=tire_plan,
        finished=finished,
        retiredLap=retired_lap,
    )


def build_geo(name, w, h):
    w = max(260, int(w))
    h = max(180, int(h))
    margin = max(28, min(w, h) * 0.10)
    if REAL_TRACKS.get(name):
        pts = REAL_TRACKS[name]["pointsMeters"]
        mnx, mxx = min(p["x"] for p in pts), max(p["x"] for p in pts)
        mny, mxy = min(p["y"] for p in pts), max(p["y"] for p in pts)
        s = min((w - 2 * margin) / max(1e-6, mxx - mnx), (h - 2 * margin) / max(1e-6, mxy - mny))
        ox = (w - (mxx - mnx) * s) * 0.5
        oy = (h - (mxy - mny) * s) * 0.5
        m = [dict(x=ox + (p["x"] - mnx) * s, y=oy + (mxy - p["y"]) * s) for p in pts]
        m += [dict(x=ox + (pts[0]["x"] - mnx) * s, y=oy + (mxy - pts[0]["y"]) * s)]
    else:
        pf = {
            "Monza": (0.22, 0.08, 1.18, 0.78, 0.2, 1.3),
            "Silverstone": (0.28, 0.12, 1.03, 0.86, 0.8, 2.2),
            "Spa-Francorchamps": (0.34, 0.14, 1.05, 0.82, 0.55, 1.85),
            "Interlagos": (0.18, 0.16, 0.98, 0.83, 1.2, 2.65),
            "Suzuka": (0.30, 0.20, 1.02, 0.88, 2.0, 0.3),
        }.get(name, (0.25, 0.1, 1, 0.85, 0, 1))
        a1, a2, kx, ky, p1, p2 = pf
        n, cx, cy, sx, sy = 900, w * 0.5, h * 0.52, w * 0.34, h * 0.33
        m = []
        for i in range(n + 1):
            t = i / n * math.pi * 2
            r = 1 + a1 * math.sin(2 * t + p1) + a2 * math.sin(3 * t + p2)
            m.append(
                dict(
                    x=cx + sx * r * kx * math.cos(t) + sx * 0.08 * math.sin(4 * t + 0.3),
                    y=cy + sy * r * ky * math.sin(t) + sy * 0.05 * math.cos(3 * t + 1.1),
                )
            )
    cum, tot = [0], 0
    for i in range(1, len(m)):
        tot += math.hypot(m[i]["x"] - m[i - 1]["x"], m[i]["y"] - m[i - 1]["y"])
        cum.append(tot)
    return dict(points=m, cum=cum, total=tot)


def point_at(geo, p):
    s = clamp(p, 0, 1) * geo["total"]
    lo, hi = 0, len(geo["cum"]) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if geo["cum"][mid] < s:
            lo = mid + 1
        else:
            hi = mid
    i = int(clamp(lo, 1, len(geo["cum"]) - 1))
    s0, s1 = geo["cum"][i - 1], geo["cum"][i]
    k = (s - s0) / max(1e-6, s1 - s0)
    p0, p1 = geo["points"][i - 1], geo["points"][i]
    return dict(x=p0["x"] + (p1["x"] - p0["x"]) * k, y=p0["y"] + (p1["y"] - p0["y"]) * k, ang=math.atan2(p1["y"] - p0["y"], p1["x"] - p0["x"]))


def state_at(res, track, tr):
    if tr <= 0:
        f = res["laps"][0]
        return dict(lap=1, pRace=0, speed=f["segV"]["straight"], pit=False, tire=f.get("tire", "-"))
    if tr >= res["total"]:
        l = res["laps"][-1]
        return dict(lap=len(res["laps"]), pRace=1, speed=l["segV"]["slow"], pit=False, tire=l.get("tire", "-"))
    fr, acc = [], 0
    for s in track["segments"]:
        acc += s["distanceKm"] / track["lapDistanceKm"]
        fr.append((s["type"], acc))
    sm = 0
    for i, lap in enumerate(res["laps"]):
        if sm + lap["time"] >= tr:
            p = (tr - sm) / lap["time"]
            stype = "slow"
            for tp, lim in fr:
                if p <= lim:
                    stype = tp
                    break
            return dict(lap=i + 1, pRace=(i + p) / len(res["laps"]), speed=lap["segV"][stype], pit=lap["pit"] and p > 0.86, tire=lap.get("tire", "-"))
        sm += lap["time"]
    return dict(lap=len(res["laps"]), pRace=1, speed=0, pit=False, tire=res["laps"][-1].get("tire", "-"))

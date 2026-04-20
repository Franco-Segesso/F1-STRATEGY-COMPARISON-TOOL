import math
import os
import random

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


def session_adjustments(session_name):
    """Session-specific car usage model layered on top of the base setup."""
    session_key = str(session_name or "R").upper()
    profiles = {
        "Q": dict(powerFactor=1.010, ersFactor=1.050, dragFactor=0.994, gripFactor=1.015),
        "SQ": dict(powerFactor=1.008, ersFactor=1.040, dragFactor=0.996, gripFactor=1.012),
        "S": dict(powerFactor=1.004, ersFactor=1.020, dragFactor=0.998, gripFactor=1.006),
        "R": dict(powerFactor=1.000, ersFactor=1.000, dragFactor=1.000, gripFactor=1.000),
    }
    return profiles.get(session_key, profiles["R"])


def normalize_tire_plan(cfg):
    stops = max(0, int(cfg.get("stops", 0)))
    plan = [cfg["tireName"]]
    for idx in range(1, stops + 1):
        key = f"pitTire{idx}"
        plan.append(cfg.get(key) or plan[-1])
    return plan


def compute_accel(params, seg, state, track, v, dt=0.05):
    """Compute dv/dt from the current car state for both Euler and RK4."""
    base_radius = {"straight": 12000, "fast": 170, "slow": 72}[seg["type"]]
    top_speed = params["topSpeedMS"] * (0.985 if seg["type"] == "straight" else 0.88 if seg["type"] == "fast" else 0.72)
    v = max(14, min(params["topSpeedMS"], v))
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
    return accel


def integrate_euler(params, seg, state, track):
    """Explicit Euler integrator over dx/dt=v and dv/dt=a(...) with fixed dt."""
    dist, dt = seg["distanceKm"] * 1000, 0.05
    x, v, t = 0, max(22, state["vEntry"]), 0
    while x < dist:
        accel = compute_accel(params, seg, state, track, v, dt)
        v = max(14, min(params["topSpeedMS"], v + accel * dt))
        x += v * dt
        t += dt
        if t > 220:
            break
    return dict(t=t, vOut=v)


def integrate_rk4(params, seg, state, track):
    """Classical RK4 integrator over the first-order system dx/dt=v, dv/dt=a(...)."""
    dist, dt = seg["distanceKm"] * 1000, 0.05
    x, v, t = 0, max(22, state["vEntry"]), 0
    while x < dist:
        def rhs(local_v):
            bounded_v = max(14, min(params["topSpeedMS"], local_v))
            return bounded_v, compute_accel(params, seg, state, track, bounded_v, dt)

        k1x, k1v = rhs(v)
        k2x, k2v = rhs(v + 0.5 * dt * k1v)
        k3x, k3v = rhs(v + 0.5 * dt * k2v)
        k4x, k4v = rhs(v + dt * k3v)

        x += (dt / 6.0) * (k1x + 2 * k2x + 2 * k3x + k4x)
        v += (dt / 6.0) * (k1v + 2 * k2v + 2 * k3v + k4v)
        v = max(14, min(params["topSpeedMS"], v))
        t += dt
        if t > 220:
            break
    return dict(t=t, vOut=v)


def get_integrator(method_name):
    method = (method_name or "Euler").strip().lower()
    if method == "rk4":
        return integrate_rk4
    return integrate_euler


def _stable_seed(cfg):
    token = "|".join(
        [
            str(cfg.get("trackName", "")),
            str(cfg.get("teamName", "")),
            str(cfg.get("driverName", "")),
            str(cfg.get("tireName", "")),
            str(cfg.get("weather", "")),
            str(cfg.get("seed", "")),
        ]
    )
    acc = 0
    for idx, ch in enumerate(token):
        acc += (idx + 1) * ord(ch)
    return acc % (2 ** 31 - 1)


def _tire_temp_factor(temp_c):
    optimum = 98.0
    delta = abs(temp_c - optimum)
    return clamp(1.0 - 0.0032 * delta, 0.82, 1.02)


def _wear_grip_factor(wear_pct):
    return clamp(1.0 - 0.0037 * wear_pct, 0.68, 1.0)


def _weather_temp_shift(weather_name):
    if weather_name == "hot":
        return 8.0
    if weather_name == "cool":
        return -6.0
    if weather_name == "wet":
        return -10.0
    if weather_name == "damp":
        return -4.0
    return 0.0


def _event_from_overspeed(rng, overspeed_ratio, skill, aggression, consistency):
    if overspeed_ratio <= 0:
        return None
    base = overspeed_ratio * (0.44 + 0.40 * aggression) * (1.08 - 0.58 * consistency)
    crash_prob = clamp(base * (1.30 - skill) * 0.30, 0.0, 0.45)
    spin_prob = clamp(base * (1.15 - 0.35 * skill) * 0.62, 0.0, 0.65)
    drag_prob = clamp(base * 0.72, 0.0, 0.72)
    roll = rng.random()
    if roll < crash_prob:
        return dict(type="choque", penalty=0.0, speedMult=0.30, finished=False)
    if roll < crash_prob + spin_prob:
        penalty = 0.8 + 2.8 * overspeed_ratio + 0.7 * (1.0 - consistency)
        speed_mult = clamp(0.70 - 0.28 * overspeed_ratio, 0.48, 0.76)
        return dict(type="derrape", penalty=penalty, speedMult=speed_mult, finished=True)
    if roll < crash_prob + spin_prob + drag_prob:
        penalty = 0.3 + 1.7 * overspeed_ratio
        speed_mult = clamp(0.84 - 0.18 * overspeed_ratio, 0.64, 0.90)
        return dict(type="drag", penalty=penalty, speedMult=speed_mult, finished=True)
    return None


def _segment_exit_multiplier(seg_type, prep_lap=False):
    if prep_lap:
        return 0.68 if seg_type == "slow" else 0.80 if seg_type == "fast" else 0.88
    return 0.72 if seg_type == "slow" else 0.85 if seg_type == "fast" else 0.91


def _simulate_prep_lap(params, integrator, track, tire, weather_name, session, fuel, tire_wear, tire_temp, pilot_skill, pilot_aggression):
    prep_t = 0.0
    vc = 0.0
    weather = WEATHER[weather_name]
    for seg in track["segments"]:
        prep_params = dict(params)
        grip_factor = _wear_grip_factor(tire_wear) * _tire_temp_factor(tire_temp)
        prep_params["gripEff"] = tire["grip"] * weather["gripFactor"] * tire["warmup"] * session["gripFactor"] * grip_factor
        prep_params["powerW"] *= 0.92
        prep_params["ersW"] *= 0.65
        prep_params["cornerFactor"] *= clamp(0.93 + 0.02 * pilot_skill + 0.02 * pilot_aggression, 0.90, 0.98)

        result = integrator(prep_params, seg, dict(fuel=fuel, wear=tire_wear, vEntry=vc), track)
        prep_t += result["t"] * 1.02
        vc = result["vOut"] * _segment_exit_multiplier(seg["type"], prep_lap=True)

        temp_target = 100.0 + _weather_temp_shift(weather_name)
        temp_gain = {"straight": 1.1, "fast": 2.3, "slow": 3.2}[seg["type"]] * (0.95 + 0.22 * pilot_aggression)
        tire_temp += (temp_target - tire_temp) * 0.10 + temp_gain
        tire_temp = clamp(tire_temp, 55.0, 125.0)

        wear_gain = tire["wear"] * track["tyreStress"] * (0.045 + 0.030 * pilot_aggression)
        tire_wear = clamp(tire_wear + wear_gain, 0.0, 100.0)

    return dict(
        prepLapTime=prep_t,
        startV=clamp(vc, 45.0, 102.0),
        tireTemp=tire_temp,
        tireWear=tire_wear,
    )


def simulate(cfg):
    weather_name = cfg.get("weather", "dry")
    w, track = WEATHER[weather_name], track_layout(cfg["trackName"])
    ref = reference_adjustments(cfg["trackName"], cfg["teamName"])
    sess = session_adjustments(cfg.get("sessionName", "Q"))
    team = TEAMS.get(cfg["teamName"], {})
    tire_name = cfg["tireName"]
    tire = TIRES[tire_name]

    pilot_skill = clamp(float(cfg.get("pilotSkill", 0.84)), 0.35, 1.0)
    pilot_aggression = clamp(float(cfg.get("pilotAggression", 0.72)), 0.0, 1.0)
    pilot_consistency = clamp(float(cfg.get("pilotConsistency", 0.80)), 0.0, 1.0)
    tire_temp = clamp(float(cfg.get("tireTempC", 95.0)), 45.0, 145.0)
    tire_wear = clamp(float(cfg.get("tireWearPct", 4.0)), 0.0, 100.0)
    max_start_wear = clamp(float(cfg.get("maxStartWearPct", 78.0)), 30.0, 100.0)
    fuel = max(1.0, float(cfg.get("fuel", 5.5)))

    top_speed_kph = ref.get("topSpeedKph") or float(cfg.get("topSpeedKph", 338.0))
    p = dict(
        powerW=float(cfg.get("power", team.get("power", 760))) * 1000 * sess["powerFactor"],
        ersW=float(cfg.get("ers", team.get("ers", 1.0))) * 120000 * sess["ersFactor"],
        mass=float(cfg.get("mass", team.get("mass", 770))),
        dragEff=float(cfg.get("drag", team.get("drag", 0.84))) * w["dragFactor"] * sess["dragFactor"],
        downforce=float(cfg.get("downforce", team.get("downforce", 1.15))) * 1.55,
        traction=float(cfg.get("traction", team.get("traction", 1.12))),
        brakeMS2=float(cfg.get("brake", team.get("brake", 1.12))) * 11.8 * track["brakeStress"],
        gripEff=tire["grip"] * w["gripFactor"] * tire["warmup"] * sess["gripFactor"],
        cornerFactor=(1.0 + 0.06 * (float(cfg.get("downforce", team.get("downforce", 1.15))) - 1.0)),
        topSpeedMS=(top_speed_kph * w["topSpeedFactor"]) / 3.6,
    )

    if tire_wear > max_start_wear:
        failed_lap = dict(
            lap=1,
            segV=dict(straight=0, fast=0, slow=0),
            segStats={k: dict(d=0, t=0) for k in ("straight", "fast", "slow")},
            pit=False,
            tire=tire_name,
            time=0.0,
            wear=tire_wear,
            fuel=fuel,
            tireTemp=tire_temp,
            events=["neumatico_excesivamente_gastado"],
        )
        return dict(
            laps=[failed_lap],
            total=0.0,
            best=float("inf"),
            avgSegment=dict(straight=0, fast=0, slow=0),
            pitLaps=[],
            tirePlan=[tire_name],
            finished=False,
            retiredLap=1,
            integrationMethod=cfg.get("integrationMethod", "Euler"),
            sessionName=cfg.get("sessionName", "Q"),
            finalSegmentExitSpeed=0.0,
            eventCounts=dict(neumatico_excesivamente_gastado=1),
            eventPenalty=0.0,
        )

    rng = random.Random(_stable_seed(cfg))
    integrator = get_integrator(cfg.get("integrationMethod", "RK4"))
    prep = _simulate_prep_lap(
        p,
        integrator,
        track,
        tire,
        weather_name,
        sess,
        fuel,
        tire_wear,
        tire_temp,
        pilot_skill,
        pilot_aggression,
    )
    start_v_entry = prep["startV"]
    tire_temp = prep["tireTemp"]
    tire_wear = prep["tireWear"]

    ld = dict(
        lap=1,
        segV=dict(straight=0, fast=0, slow=0),
        segStats={k: dict(d=0, t=0) for k in ("straight", "fast", "slow")},
        pit=False,
        tire=tire_name,
        events=[],
    )
    event_counts = dict(derrape=0, drag=0, choque=0, frenada_temprana=0)
    event_penalty = 0.0
    last_v_out = start_v_entry
    lap_t = 0.0
    vc = start_v_entry
    finished = True

    for seg in track["segments"]:
        grip_factor = _wear_grip_factor(tire_wear) * _tire_temp_factor(tire_temp)
        p["gripEff"] = tire["grip"] * w["gripFactor"] * tire["warmup"] * sess["gripFactor"] * grip_factor
        p["cornerFactor"] = (1.0 + 0.06 * (float(cfg.get("downforce", team.get("downforce", 1.15))) - 1.0))
        p["cornerFactor"] *= 1.0 - 0.050 * (1.0 - pilot_skill) + 0.028 * pilot_aggression
        p["cornerFactor"] = clamp(p["cornerFactor"], 0.86, 1.08)

        r = integrator(p, seg, dict(fuel=fuel, wear=tire_wear, vEntry=vc), track)
        seg_time = r["t"]

        if seg["type"] != "straight":
            early_brake = clamp((1.0 - pilot_skill) * (1.0 - 0.60 * pilot_aggression), 0.0, 0.10)
            if early_brake > 0.01:
                penalty = seg_time * early_brake
                seg_time += penalty
                event_penalty += penalty
                event_counts["frenada_temprana"] += 1
                vc *= clamp(1.0 - 0.26 * early_brake, 0.86, 1.0)

            base_radius = 170.0 if seg["type"] == "fast" else 72.0
            safe_v = math.sqrt(max(25.0, p["gripEff"] * G * base_radius)) * p["cornerFactor"]
            target_mult = 0.98 + 0.08 * pilot_aggression - 0.05 * (1.0 - pilot_skill)
            target_v = safe_v * target_mult
            overspeed_ratio = max(0.0, (vc - target_v) / max(target_v, 1e-6))
            event = _event_from_overspeed(rng, overspeed_ratio, pilot_skill, pilot_aggression, pilot_consistency)
            if event:
                event_counts[event["type"]] = event_counts.get(event["type"], 0) + 1
                ld["events"].append(event["type"])
                if event["penalty"] > 0:
                    seg_time += event["penalty"]
                    event_penalty += event["penalty"]
                vc *= event.get("speedMult", 1.0)
                if not event["finished"]:
                    finished = False

        lap_t += seg_time
        vc = max(vc, 14.0)
        vc = min(r["vOut"], vc) * _segment_exit_multiplier(seg["type"], prep_lap=False)
        last_v_out = r["vOut"]
        ld["segStats"][seg["type"]]["d"] += seg["distanceKm"] * 1000
        ld["segStats"][seg["type"]]["t"] += seg_time

        temp_target = 95.0 + _weather_temp_shift(weather_name)
        temp_gain = {"straight": 0.9, "fast": 2.0, "slow": 2.8}[seg["type"]] * (0.90 + 0.30 * pilot_aggression)
        tire_temp += (temp_target - tire_temp) * 0.06 + temp_gain
        tire_temp = clamp(tire_temp, 45.0, 150.0)

        wear_gain = tire["wear"] * track["tyreStress"] * (0.13 + 0.08 * pilot_aggression)
        wear_gain *= 1.0 + max(0.0, (tire_temp - 110.0)) / 45.0
        tire_wear = clamp(tire_wear + wear_gain, 0.0, 100.0)

        if not finished:
            break

    for k, ss in ld["segStats"].items():
        ld["segV"][k] = (ss["d"] / ss["t"]) * 3.6 if ss["t"] > 0 else 0
    ld["time"], ld["wear"], ld["fuel"], ld["tireTemp"] = lap_t, tire_wear, fuel, tire_temp
    avg = dict(ld["segV"])

    return dict(
        laps=[ld],
        total=lap_t,
        best=lap_t if finished else float("inf"),
        avgSegment=avg,
        pitLaps=[],
        tirePlan=[tire_name],
        finished=finished,
        retiredLap=(None if finished else 1),
        integrationMethod=cfg.get("integrationMethod", "Euler"),
        sessionName=cfg.get("sessionName", "Q"),
        finalSegmentExitSpeed=last_v_out,
        prepLapTime=prep["prepLapTime"],
        flyingStartSpeedKph=start_v_entry * 3.6,
        eventCounts=event_counts,
        eventPenalty=event_penalty,
    )


def build_geo(name, w, h):
    w = max(260, int(w))
    h = max(180, int(h))
    margin = max(28, min(w, h) * 0.10)
    if REAL_TRACKS.get(name):
        pts = [
            p for p in REAL_TRACKS[name]["pointsMeters"]
            if math.isfinite(p["x"]) and math.isfinite(p["y"])
        ]
        if len(pts) < 8:
            REAL_TRACKS[name] = None
            return build_geo(name, w, h)
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
    if not math.isfinite(tot) or tot <= 0:
        return None
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

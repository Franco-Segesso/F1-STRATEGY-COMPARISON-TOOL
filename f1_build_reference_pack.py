import argparse
import os

from f1_core import CACHE_DIR
from f1_data import TRACK_EVENT_ALIASES, TRACKS
from f1_fetch_real_data import build_reference


DEFAULT_SESSIONS = ["Q", "R", "SQ", "S"]


def build_pack(year, sessions, tracks):
    os.makedirs(CACHE_DIR, exist_ok=True)
    built = []
    failed = []
    for track in tracks:
        aliases = TRACK_EVENT_ALIASES.get(track, [track])
        event = aliases[0]
        for session in sessions:
            try:
                csv_path, json_path = build_reference(year, event, session, CACHE_DIR, output_name=track)
                built.append((track, session, csv_path, json_path))
                print(f"OK  {track} {session} -> {os.path.basename(json_path)}")
            except Exception as exc:
                failed.append((track, session, str(exc)))
                print(f"ERR {track} {session} -> {exc}")
    return built, failed


def main():
    parser = argparse.ArgumentParser(description="Construye un pack local de referencias FastF1 para uso offline.")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--sessions", nargs="+", default=DEFAULT_SESSIONS)
    parser.add_argument("--tracks", nargs="+", default=list(TRACKS.keys()))
    args = parser.parse_args()

    built, failed = build_pack(args.year, args.sessions, args.tracks)
    print(f"\nGeneradas: {len(built)}")
    print(f"Fallidas: {len(failed)}")
    if failed:
        print("Pendientes:")
        for track, session, err in failed:
            print(f"- {track} {session}: {err}")


if __name__ == "__main__":
    main()

"""Recreate local directories that Git does not store when they are empty."""

from nascente_brasil.paths import required_directories


def main() -> int:
    directories = required_directories()
    for path in directories:
        path.mkdir(parents=True, exist_ok=True)
    print(f"Phase 1 directories ready: {len(directories)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

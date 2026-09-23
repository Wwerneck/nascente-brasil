from __future__ import annotations

import logging
from uuid import uuid4

from nascente_brasil.config import get_settings
from nascente_brasil.logging_config import configure_logging, get_logger
from nascente_brasil.metadata.manifest import validate_manifest_header
from nascente_brasil.paths import required_directories


def main() -> int:
    settings = get_settings()
    settings.validate()
    log_path = configure_logging(settings)
    logger = get_logger("phase_1")
    run_id = str(uuid4())

    missing_directories = [path for path in required_directories() if not path.exists()]
    if missing_directories:
        logger.error(
            "Required directories are missing",
            extra={
                "run_id": run_id,
                "pipeline": "phase_1_foundation",
                "task": "validate_structure",
                "status": "failed",
                "error": ", ".join(str(path) for path in missing_directories),
            },
        )
        return 1

    validate_manifest_header(settings.manifest_path)

    logger.info(
        "Phase 1 foundation validation completed",
        extra={
            "run_id": run_id,
            "pipeline": "phase_1_foundation",
            "task": "validate_phase_1",
            "source": "foundation",
            "file": str(settings.manifest_path),
            "rows_in": 0,
            "rows_out": 0,
            "rows_invalid": 0,
            "status": "success",
        },
    )
    logging.getLogger("nascente_brasil").handlers[0].flush()
    print(f"Phase 1 validation succeeded. Log file: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

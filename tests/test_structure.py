from __future__ import annotations

from nascente_brasil.metadata.manifest import MANIFEST_COLUMNS, read_manifest_header
from nascente_brasil.paths import required_directories
from nascente_brasil.config import get_settings


def test_required_directories_exist() -> None:
    missing = [path for path in required_directories() if not path.exists()]
    assert missing == []


def test_ingestion_manifest_has_governance_columns() -> None:
    settings = get_settings()
    assert read_manifest_header(settings.manifest_path) == MANIFEST_COLUMNS


def test_foundation_documentation_exists() -> None:
    root = get_settings().root_dir
    docs = [
        root / "README.md",
        root / "docker-compose.yml",
        root / "docs" / "architecture" / "foundation.md",
        root / "docs" / "methodology" / "phases.md",
        root / "docs" / "checkpoints" / "phase_1_foundation.md",
        root / "docs" / "data_quality" / "schema_changes.md",
        root / "docs" / "sources" / "source_governance.md",
        root / "docs" / "lineage" / "lineage.md",
    ]
    missing = [path for path in docs if not path.exists() or path.stat().st_size == 0]
    assert missing == []

from pathlib import Path

from app.utils.uploads import get_crew_crop_static_path


def test_get_crew_crop_static_path_returns_path_when_file_exists(tmp_path):
    root = tmp_path / "crew-crops"
    root.mkdir(parents=True, exist_ok=True)
    (root / "crop-1.png").write_bytes(b"png-bytes")

    assert get_crew_crop_static_path("crop-1", upload_root=str(root)) == "/uploads/crew-crops/crop-1.png"


def test_get_crew_crop_static_path_returns_none_when_file_missing(tmp_path):
    root = tmp_path / "crew-crops"
    root.mkdir(parents=True, exist_ok=True)

    assert get_crew_crop_static_path("missing-crop", upload_root=str(root)) is None

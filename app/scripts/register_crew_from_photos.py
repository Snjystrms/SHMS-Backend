"""
Register crew members from photos in the photos/ folder.
Uses the file name (without extension) as the crew member name.
Requires one clear face per image. Skips duplicate faces and invalid images.

Run from project root:
  python -m app.scripts.register_crew_from_photos

Optional: pass a custom folder path:
  python -m app.scripts.register_crew_from_photos /path/to/photos
"""
import argparse
import sys
from pathlib import Path

# Ensure project root is on path when run as __main__
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app.core.config import settings
from app.services import face_service

# Image extensions to consider
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def get_photo_files(photos_dir: Path):
    """Yield (path, name) for each image file. Name = stem (filename without extension)."""
    if not photos_dir.is_dir():
        return
    for path in sorted(photos_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path, path.stem


def main(photos_dir: Path) -> None:
    print(f"Scanning photos in: {photos_dir}")
    registered = 0
    skipped_no_face = []
    skipped_name_exists = []
    skipped_duplicate_face = []
    errors = []

    for path, name in get_photo_files(photos_dir):
        image_bytes = path.read_bytes()
        embedding = face_service.get_embedding(image_bytes)

        if embedding is None:
            skipped_no_face.append(name)
            print(f"  Skip {name}: no face detected in {path.name}")
            continue

        if face_service.get_user_id_by_name(name):
            skipped_name_exists.append(name)
            print(f"  Skip {name}: crew member with this name already exists")
            continue

        _, existing_name, distance = face_service.find_match(embedding)
        if distance is not None and distance < settings.FACE_DUPLICATE_THRESHOLD:
            skipped_duplicate_face.append((name, existing_name))
            print(f"  Skip {name}: face already registered as {existing_name}")
            continue

        crew_member_id = face_service.register_user(
            name,
            embedding,
            aadhaar_number=None,
            contact_number=None,
            emergency_contact_number=None,
            is_pilot=False,
        )
        if crew_member_id:
            registered += 1
            print(f"  Registered: {name} (id={crew_member_id})")
        else:
            errors.append(name)
            print(f"  Error: failed to register {name}")

    print()
    print(f"Done. Registered: {registered}")
    if skipped_no_face:
        print(f"Skipped (no face): {', '.join(skipped_no_face)}")
    if skipped_name_exists:
        print(f"Skipped (name already exists): {', '.join(skipped_name_exists)}")
    if skipped_duplicate_face:
        print(f"Skipped (duplicate face): {', '.join(n for n, _ in skipped_duplicate_face)}")
    if errors:
        print(f"Errors: {', '.join(errors)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register crew members from photos (filename = name)")
    parser.add_argument(
        "photos_dir",
        nargs="?",
        default=_project_root / "photos",
        type=Path,
        help="Folder containing photo files (default: project_root/photos)",
    )
    args = parser.parse_args()
    photos_dir = args.photos_dir.resolve()
    if not photos_dir.exists():
        print(f"Error: folder does not exist: {photos_dir}")
        sys.exit(1)
    main(photos_dir)

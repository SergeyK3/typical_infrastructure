#!/usr/bin/env python3
"""Verify Google Drive config for psych testing (prod checklist)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check psych-testing Google Drive setup")
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Call Drive API (list root folder metadata)",
    )
    args = parser.parse_args()

    from psychological_testing.integration.report_storage import gdrive_enabled, storage_status

    st = storage_status()
    print("PSYCH_TESTING_GDRIVE enabled:", st["gdrive_enabled"])
    print("Configured (SA + folder id):", st["gdrive_configured"])
    print("Storage label:", st.get("storage_label", ""))

    if not st["gdrive_enabled"]:
        print("OK: Drive upload disabled (local cache only).")
        return 0

    if not st["gdrive_configured"]:
        print(
            "ERROR: PSYCH_TESTING_GDRIVE=1 but SA JSON or "
            "PSYCH_TESTING_GDRIVE_FOLDER_ID is missing.",
            file=sys.stderr,
        )
        return 1

    import os

    from psychological_testing.env import load_plugin_env

    load_plugin_env(override=False)
    sa_path = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "").strip()
    if sa_path:
        p = Path(sa_path)
        print("SA JSON path:", p)
        if not p.is_file():
            print(f"ERROR: service account file not found: {p}", file=sys.stderr)
            return 1
        if str(p).startswith("\\\\") or sa_path.startswith("//"):
            print("Note: UNC/network path — ensure the app service account can read it.")

    if not args.probe:
        print("Dry run OK. Re-run with --probe to test Drive API.")
        return 0

    try:
        from psychological_testing.integration import google_drive_client as gdrive

        service = gdrive._build_drive_service()
        folder_id = gdrive.root_folder_id()
        meta = (
            service.files()
            .get(fileId=folder_id, fields="id,name,mimeType", supportsAllDrives=True)
            .execute()
        )
        print("Drive probe OK:", meta.get("name") or meta.get("id"))
        return 0
    except Exception as exc:
        print(f"ERROR: Drive probe failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

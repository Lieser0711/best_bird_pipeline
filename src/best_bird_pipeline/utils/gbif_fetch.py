
import argparse
import json
import shutil
import time
import zipfile
from pathlib import Path

import requests

API_URL = "https://api.gbif.org/v1/occurrence/download"
OUTPUT_DIR = Path("data/raw/gbif")
POLL_INTERVAL = 60  # Sekunden
MAX_WAIT = 6 * 60 * 60  # maximal 6 Stunden


def get_download_status(download_key):
    """Download-Status und Metadaten von GBIF abrufen."""
    url = f"{API_URL}/{download_key}"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    return response.json()


def wait_for_download(download_key):
    """Warten, bis GBIF den Download fertiggestellt hat."""
    start_time = time.monotonic()

    while time.monotonic() - start_time < MAX_WAIT:
        metadata = get_download_status(download_key)
        status = metadata["status"]

        print(f"Download-Status: {status}")

        if status == "SUCCEEDED":
            return metadata

        if status in {"FAILED", "KILLED", "CANCELLED"}:
            raise RuntimeError(
                f"GBIF-Download nicht erfolgreich: {status}"
            )

        time.sleep(POLL_INTERVAL)

    raise TimeoutError("Maximale Wartezeit überschritten.")


def download_zip(download_url, destination):
    """ZIP-Datei herunterladen, ohne sie komplett in RAM zu laden."""
    temp_path = destination.with_suffix(".zip.part")

    with requests.get(
        download_url,
        stream=True,
        timeout=(30, 120),
    ) as response:
        response.raise_for_status()

        with open(temp_path, "wb") as file:
            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):
                if chunk:
                    file.write(chunk)

    temp_path.replace(destination)


def extract_occurrences(zip_path, output_dir):
    """Extrahiert die CSV-Datei aus dem GBIF-Download."""

    output_path = output_dir / "occurrences.csv"

    with zipfile.ZipFile(zip_path) as archive:

        candidates = [
            name for name in archive.namelist()
            if name.lower().endswith(".csv")
            and not name.startswith("__MACOSX/")
        ]

        if len(candidates) != 1:
            raise ValueError(
                f"CSV-Datei nicht eindeutig: {candidates}"
            )

        with archive.open(candidates[0]) as source:
            with open(output_path, "wb") as target:
                shutil.copyfileobj(source, target)

    print(f"Datei erfolgreich gespeichert: {output_path}")

    return output_path


def main(download_key):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Warte auf GBIF-Download {download_key}")

    metadata = wait_for_download(download_key)

    download_url = metadata.get("downloadLink")

    if not download_url:
        raise ValueError("Keine Download-URL vorhanden.")

    zip_path = OUTPUT_DIR / f"{download_key}.zip"

    print("Lade ZIP-Datei herunter...")
    download_zip(download_url, zip_path)

    print("Entpacke Beobachtungsdaten...")
    output_path = extract_occurrences(zip_path, OUTPUT_DIR)

    metadata_path = OUTPUT_DIR / f"{download_key}_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print(f"Fertig! Daten gespeichert: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "download_key",
        help="GBIF-Download-ID",
    )
    args = parser.parse_args()

    main(args.download_key)

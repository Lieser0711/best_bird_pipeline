import os
import json
from pathlib import Path

import requests
from dotenv import load_dotenv

from gbif_fetch import main as fetch_download

load_dotenv()
API = 'https://api.gbif.org/v1'
BIRDS = {
    'Amsel': 'Turdus merula',
    'Kohlmeise': 'Parus major',
    'Rotkehlchen': 'Erithacus rubecula',
    'Haussperling': 'Passer domesticus',
    'Kranich': 'Grus grus',
    'Rauchschwalbe': 'Hirundo rustica',
    'Weißstorch': 'Ciconia ciconia',
    'Mauersegler': 'Apus apus',
    'Bienenfresser': 'Merops apiaster',
    'Eisvogel': 'Alcedo atthis',
    'Seeadler': 'Haliaeetus albicilla',
    'Kiebitz': 'Vanellus vanellus',
}

def taxon_keys():
    keys = {}
    for common, scientific in BIRDS.items():
        response = requests.get(f'{API}/species/match', params={'name': scientific, 'strict': 'true'}, timeout=30)
        response.raise_for_status()
        item = response.json()
        if item.get('rank') != 'SPECIES' or item.get('matchType') == 'NONE' or not item.get('usageKey'):
            raise ValueError(f'Cannot resolve species: {scientific}: {item}')
        keys[scientific] = item.get('acceptedUsageKey') or item['usageKey']
        print(f'{common}: {scientific} -> {keys[scientific]}')
    if len(set(keys.values())) != len(keys):
        raise ValueError('Multiple names resolved to same taxon key; inspect taxonomy.')
    return keys

def submit_download(keys, date):
    username, password, email = (
        os.getenv(x)
        for x in ('GBIF_USERNAME', 'GBIF_PASSWORD', 'GBIF_EMAIL')
    )
    if not all((username, password, email)):
        raise RuntimeError(
            'Set GBIF_USERNAME, GBIF_PASSWORD, GBIF_EMAIL in .env'
        )
    payload = {
        'creator': username,
        'notificationAddresses': [email],
        'sendNotification': True,
        'format': 'SIMPLE_CSV',
        'predicate': {
            'type': 'and',
            'predicates': [
            {
                'type': 'in',
                'key': 'TAXON_KEY',
                'values': list(keys.values())
            },
            {
                'type': 'equals',
                'key': 'COUNTRY',
                'value': 'DE'
            },
            {
                'type': 'equals',
                'key': 'BASIS_OF_RECORD',
                'value': 'HUMAN_OBSERVATION'
            },
            {
                'type': 'equals',
                'key': 'OCCURRENCE_STATUS',
                'value': 'PRESENT'
            },
            {
                'type': 'equals',
                'key': 'EVENT_DATE',
                'value': date},
        ]},
    }
    Path('data/raw/gbif').mkdir(parents=True, exist_ok=True)
    Path('data/raw/gbif/download_request.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')

    print("Username:", os.getenv("GBIF_USERNAME"))
    print("Password vorhanden:", bool(os.getenv("GBIF_PASSWORD")))
    print("Email:", os.getenv("GBIF_EMAIL"))

    response = requests.post(
    f'{API}/occurrence/download/request',
    json=payload,
    auth=(username, password),
    timeout=60
)

    print("Status:", response.status_code)
    print("Antwort:", response.text[:1000])
    print("WWW-Authenticate:", response.headers.get("WWW-Authenticate"))

    response.raise_for_status()

    key = response.text.strip().strip('"')

    Path('data/raw/gbif/download_key.txt').write_text(key, encoding='utf-8')
    print(f'Download submitted: {key}')
    print(f'Check status: {API}/occurrence/download/{key}')
    return key

if __name__ == '__main__':
    
    date = '2025-01-01'

    key_path = Path('data/raw/gbif/download_key.txt')

    if key_path.exists():

        # Vorhandenen Download fortsetzen
        download_key = key_path.read_text(
            encoding='utf-8'
        ).strip()

        print(f"Existing download: {download_key}")

    else:

        # Neuen Download anfordern
        keys = taxon_keys()
        download_key = submit_download(keys, date)

    # Download abholen
    fetch_download(download_key)

    print("GBIF-Daten erfolgreich heruntergeladen!")
from argparse import ArgumentParser
from datetime import datetime, timedelta, timezone

import jwt
import requests
from pathlib import Path
import os
import rich

def get_token(app_id, private_key, installation_id):
    payload = {
        "iat": datetime.now(tz=timezone.utc) - timedelta(seconds=60),
        "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=10),
        "iss": app_id,
    }

    encoded_jwt = jwt.encode(payload, Path(private_key).read_text(), algorithm="RS256")
    rich.print(encoded_jwt)
    response = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {encoded_jwt}",
        },
        timeout=60,
    )
    rich.print(response.content)
    response.raise_for_status()
    return response.json()["token"]

def cli():
    parser = ArgumentParser()
    d = os.environ['GITHUB_APP_ID'] if 'GITHUB_APP_ID' in os.environ else None

    parser.add_argument("--app-id", required=d is None, default=d)
    d = os.environ['GITHUB_APP_KEYFILE'] if 'GITHUB_APP_KEYFILE' in os.environ else None
    parser.add_argument("--private-key", required=d is None, default=d)
    d = os.environ['GITHUB_APP_INSTALLATION_ID'] if 'GITHUB_APP_INSTALLATION_ID' in os.environ else None
    if d is None:
        d = os.environ['GITHUB_INSTALLATION_ID'] if 'GITHUB_INSTALLATION_ID' in os.environ else None
    parser.add_argument("--installation-id", required=d is None, default=d)

    args = parser.parse_args()
    token = get_token(args.app_id, args.private_key, args.installation_id)

    print(token)

if __name__ == '__main__':
  cli()

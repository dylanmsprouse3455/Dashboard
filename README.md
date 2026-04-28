# snapshot.py

Signal-first public-intelligence CLI router.

## Install

```bash
python3 -m pip install -r requirements.txt
```

## Usage

```bash
python3 snapshot.py "info@example.com"
python3 snapshot.py "+14235551234"
python3 snapshot.py "example.com"
python3 snapshot.py "https://example.com"
python3 snapshot.py "Spring City Chamber"
```

## What it does

- Detects input type (email, phone, domain, url, username, business/general term).
- Runs lightweight public checks (DNS, website metadata, parsing).
- Generates public pivot links instead of scraping search engines.
- Outputs short terminal summary and saves TXT + JSON reports in `reports/`.

## Safety

- Public-source checks only.
- No login/signup/password-reset/account-recovery flows.
- No brute force directories or port scanning.
- No identity confirmation from weak matches.

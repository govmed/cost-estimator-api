#!/usr/bin/env python3
"""
Project retention cleanup utility.

Reads a YAML policy file and hard-deletes projects that match ALL criteria.
Run manually or as a cron job — NOT part of the FastAPI app.

Usage:
    python cleanup/run.py --policy cleanup/policy.example.yml [--dry-run]

Docker:
    docker compose exec api python cleanup/run.py --policy cleanup/policy.example.yml
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("pyyaml required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.models import Project  # noqa: F401 — triggers model registration


def load_policy(path: str) -> list[dict]:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("policies", [])


def matches(project: Project, rule: dict, now: datetime) -> bool:
    if "status" in rule and project.status not in rule["status"]:
        return False
    if "older_than_days" in rule:
        cutoff = now - timedelta(days=rule["older_than_days"])
        if project.updated_at.replace(tzinfo=timezone.utc) > cutoff:
            return False
    return True


def run(policy_path: str, dry_run: bool = False) -> None:
    rules = load_policy(policy_path)
    if not rules:
        print("No policies defined — nothing to do.")
        return

    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    now = datetime.now(timezone.utc)

    try:
        projects = db.query(Project).all()
        deleted = 0

        for rule in rules:
            label = rule.get("name", "unnamed")
            targets = [p for p in projects if matches(p, rule, now)]

            print(f"Policy '{label}': {len(targets)} project(s) matched")
            for p in targets:
                print(f"  {'[DRY RUN] would delete' if dry_run else 'Deleting'}: {p.id} — {p.name!r} (status={p.status})")
                if not dry_run:
                    db.delete(p)
                    deleted += 1

        if not dry_run:
            db.commit()
            print(f"\nDeleted {deleted} project(s).")
        else:
            print(f"\nDry run complete — {sum(len([p for p in projects if matches(p, r, now)]) for r in rules)} would be deleted.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Project retention cleanup")
    parser.add_argument("--policy", required=True, help="Path to YAML policy file")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be deleted without deleting")
    args = parser.parse_args()
    run(args.policy, dry_run=args.dry_run)

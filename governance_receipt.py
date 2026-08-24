#!/usr/bin/env python3
"""Create and compare compact public Snapshot governance proposal receipts.

The receipt preserves decision-relevant public metadata and a SHA-256 fingerprint
of the proposal body. It never signs, votes, submits transactions, or stores the
full proposal text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

SNAPSHOT_GRAPHQL_URL = "https://hub.snapshot.org/graphql"
PROPOSAL_ID_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")


def normalize_proposal_id(proposal_id: str) -> str:
    if not PROPOSAL_ID_RE.fullmatch(proposal_id):
        raise ValueError("proposal ID must be a 32-byte 0x-prefixed hexadecimal hash")
    return proposal_id.lower()


def iso_timestamp(value: object) -> str:
    if not isinstance(value, int) or value < 0:
        raise ValueError("Snapshot returned an invalid Unix timestamp")
    return datetime.fromtimestamp(value, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_proposal(proposal_id: str, opener=urlopen, fetched_at: str | None = None) -> dict[str, object]:
    proposal_id = normalize_proposal_id(proposal_id)
    query = """
      query ProposalReceipt($id: String!) {
        proposal(id: $id) {
          id title body choices start end snapshot state scores scores_total votes
          space { id name }
        }
      }
    """
    request = Request(
        SNAPSHOT_GRAPHQL_URL,
        data=json.dumps({"query": query, "variables": {"id": proposal_id}}, separators=(",", ":")).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "nightshift-governance-receipt"},
        method="POST",
    )
    with opener(request, timeout=20) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise ValueError(f"Snapshot query failed: {payload['errors']}")
    proposal = payload.get("data", {}).get("proposal")
    if not isinstance(proposal, dict):
        raise ValueError("Snapshot proposal was not found")

    required_strings = ("id", "title", "body", "state")
    if any(not isinstance(proposal.get(field), str) for field in required_strings):
        raise ValueError("Snapshot returned malformed proposal text fields")
    space = proposal.get("space")
    choices = proposal.get("choices")
    scores = proposal.get("scores")
    if (
        not isinstance(space, dict)
        or not isinstance(space.get("id"), str)
        or not isinstance(space.get("name"), str)
        or not isinstance(choices, list)
        or not all(isinstance(choice, str) for choice in choices)
        or not isinstance(scores, list)
        or not all(isinstance(score, (int, float)) and not isinstance(score, bool) for score in scores)
        or not isinstance(proposal.get("scores_total"), (int, float))
        or isinstance(proposal.get("scores_total"), bool)
        or not isinstance(proposal.get("votes"), int)
        or not isinstance(proposal.get("snapshot"), (int, str))
    ):
        raise ValueError("Snapshot returned malformed proposal metadata")

    source_url = f"https://snapshot.box/#/{space['id']}/proposal/{proposal_id}"
    return {
        "schema_version": 1,
        "fetched_at": fetched_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": {"api": SNAPSHOT_GRAPHQL_URL, "proposal_url": source_url},
        "proposal": {
            "id": proposal_id,
            "space": {"id": space["id"], "name": space["name"]},
            "title": proposal["title"],
            "state": proposal["state"],
            "start": iso_timestamp(proposal["start"]),
            "end": iso_timestamp(proposal["end"]),
            "snapshot_block": proposal["snapshot"],
            "choices": choices,
            "scores": scores,
            "scores_total": proposal["scores_total"],
            "votes": proposal["votes"],
            "body": {
                "characters": len(proposal["body"]),
                "sha256": hashlib.sha256(proposal["body"].encode()).hexdigest(),
            },
        },
    }


def compare_receipts(previous: dict[str, object], current: dict[str, object]) -> list[str]:
    for field in ("schema_version",):
        if previous.get(field) != current.get(field):
            raise ValueError(f"cannot compare receipts with different {field}")
    previous_proposal = previous.get("proposal")
    current_proposal = current.get("proposal")
    if not isinstance(previous_proposal, dict) or not isinstance(current_proposal, dict):
        raise ValueError("receipt has malformed proposal data")
    if previous_proposal.get("id") != current_proposal.get("id"):
        raise ValueError("cannot compare receipts for different proposals")
    changed_fields = []
    for field in ("title", "state", "start", "end", "snapshot_block", "choices", "body"):
        if previous_proposal.get(field) != current_proposal.get(field):
            changed_fields.append(field)
    return changed_fields


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", required=True, help="Snapshot proposal ID")
    parser.add_argument("--output", type=Path, help="write the current JSON receipt to this path")
    parser.add_argument("--compare", type=Path, help="compare current receipt with a prior JSON receipt")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        receipt = fetch_proposal(args.proposal)
        changes: list[str] | None = None
        if args.compare:
            changes = compare_receipts(json.loads(args.compare.read_text()), receipt)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result: dict[str, object] = {"receipt": receipt}
    if changes is not None:
        result["decision_surface_changes"] = changes
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        proposal = receipt["proposal"]
        print(f"{proposal['state']}: {proposal['title']}")  # type: ignore[index]
        print(f"{proposal['space']['name']}; ends {proposal['end']}; {proposal['votes']} votes")  # type: ignore[index]
        if changes is not None:
            print("decision-surface changes: " + (", ".join(changes) if changes else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import json
import unittest

import governance_receipt


PROPOSAL_ID = "0x" + "ab" * 32


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, *_):
        return json.dumps(self.payload).encode()


def valid_payload():
    return {
        "data": {
            "proposal": {
                "id": PROPOSAL_ID,
                "title": "Upgrade council rules",
                "body": "Public proposal body that must not be retained in the receipt.",
                "choices": ["For", "Against"],
                "start": 1784332800,
                "end": 1784419200,
                "snapshot": "12345678",
                "state": "active",
                "scores": [12.5, 3],
                "scores_total": 15.5,
                "votes": 2,
                "space": {"id": "example.eth", "name": "Example DAO"},
            }
        }
    }


class GovernanceReceiptTests(unittest.TestCase):
    def test_creates_compact_body_hashed_receipt(self):
        calls = []

        def opener(request, timeout):
            calls.append(json.loads(request.data))
            self.assertEqual(request.headers["User-agent"], "nightshift-governance-receipt")
            return FakeResponse(valid_payload())

        receipt = governance_receipt.fetch_proposal(
            PROPOSAL_ID.upper().replace("0X", "0x"), opener=opener, fetched_at="2026-07-18T00:00:00Z"
        )

        proposal = receipt["proposal"]
        self.assertEqual(proposal["id"], PROPOSAL_ID)
        self.assertEqual(proposal["start"], "2026-07-18T00:00:00Z")
        self.assertEqual(proposal["body"]["characters"], len(valid_payload()["data"]["proposal"]["body"]))
        self.assertNotIn("Public proposal body", json.dumps(receipt))
        self.assertEqual(receipt["source"]["proposal_url"], f"https://snapshot.box/#/example.eth/proposal/{PROPOSAL_ID}")
        self.assertEqual(calls[0]["variables"]["id"], PROPOSAL_ID)

    def test_compare_reports_only_decision_surface_changes(self):
        old = governance_receipt.fetch_proposal(
            PROPOSAL_ID,
            opener=lambda *_, **__: FakeResponse(valid_payload()),
            fetched_at="2026-07-18T00:00:00Z",
        )
        same = json.loads(json.dumps(old))
        self.assertEqual(governance_receipt.compare_receipts(old, same), [])
        changed = json.loads(json.dumps(old))
        changed["proposal"]["choices"] = ["For", "Against", "Abstain"]
        changed["proposal"]["scores"] = [20, 5, 1]
        self.assertEqual(governance_receipt.compare_receipts(old, changed), ["choices"])
        changed["proposal"]["id"] = "0x" + "cd" * 32
        with self.assertRaisesRegex(ValueError, "different proposals"):
            governance_receipt.compare_receipts(old, changed)

    def test_rejects_bad_id_and_malformed_payload(self):
        with self.assertRaisesRegex(ValueError, "proposal ID"):
            governance_receipt.normalize_proposal_id("not-a-proposal")
        malformed = valid_payload()
        malformed["data"]["proposal"]["votes"] = "two"
        with self.assertRaisesRegex(ValueError, "malformed proposal metadata"):
            governance_receipt.fetch_proposal(PROPOSAL_ID, opener=lambda *_, **__: FakeResponse(malformed))


if __name__ == "__main__":
    unittest.main()

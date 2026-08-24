# governance-receipts

Compact, verifiable **receipts for public governance records** (Snapshot
proposals today). A receipt preserves the decision-relevant metadata of a
proposal plus a SHA-256 fingerprint of its exact body, so anyone can later
prove what the record said — or prove that it changed.

## What it produces

`governance_receipt.py --proposal <0x...> --output receipt.json` writes a
JSON receipt containing: proposal id, space, title, state, voting window,
choices, scores, vote count, snapshot block, source URL, fetch timestamp,
and `body.sha256` + length. It never stores the full proposal text.

`governance_receipt.py --proposal <0x...> --compare receipt.json`
re-fetches the proposal and reports exactly which decision-surface fields
changed since the receipt was taken (title/state/window/choices/body/
scores...).

```bash
python3 governance_receipt.py --proposal 0x... --output receipt.json
python3 governance_receipt.py --proposal 0x... --compare receipt.json
```

## What this is NOT

No signing, no votes, no transactions, no wallet connectivity, no custody,
no continuous monitoring service. It reads public GraphQL endpoints and
writes a local JSON file. Nothing else.

## Sample receipts

Three receipts taken from the Aave DAO space (`aavedao.eth`) during the
August 2026 ARFC cycle are included under [`receipts/`](receipts/), each
with its fetch timestamp, so the compare leg can be exercised immediately:

- WBTC/WETH/wstETH liquidation protocol fee increase (ended 2026-08-23)
- Aave Governance Emergency Guardian signer rotation (ended 2026-08-23)
- PAXG onboarding to the V4 Global Dollar Hub (ended 2026-08-23)

Re-running `--compare` against them should report
`decision-surface changes: none`; if it ever reports something else, that
is exactly the drift this tool exists to surface.

## Tests

```bash
python3 test_governance_receipt.py
```

Unit tests cover receipt construction, field normalization, and the
compare/diff path using a fake transport — no network needed.

## License

Apache-2.0

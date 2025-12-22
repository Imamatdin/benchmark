import argparse, json, re
from pathlib import Path

ALLOWED_ACTIONS = {"ASK", "ANSWER", "REFUSE", "DEFER"}
ALLOWED_CONF = {"LOW", "MEDIUM", "HIGH"}
REQUIRED_KEYS = ["action", "final", "evidence", "confidence"]

def try_parse_json(text: str):
    """
    Strict: response must be a single JSON object, no surrounding prose.
    If model returns extra text, try to extract first {...} block (optional),
    but we still mark schema_strict_fail for transparency.
    """
    text_strip = text.strip()

    # Strict parse first
    try:
        obj = json.loads(text_strip)
        return obj, True, None
    except Exception as e_strict:
        # Fallback: extract first JSON object-like block
        m = re.search(r"\{.*\}", text_strip, flags=re.S)
        if not m:
            return None, False, f"no_json_object: {e_strict}"
        try:
            obj = json.loads(m.group(0))
            return obj, False, None  # parsed but not strict
        except Exception as e_loose:
            return None, False, f"bad_json: {e_loose}"

def schema_score(obj):
    # Hard gate: correct keys only, correct enums
    if not isinstance(obj, dict):
        return 0, ["not_object"]
    keys = list(obj.keys())
    if keys != REQUIRED_KEYS:
        # allow same keys different order? If you want strict order, keep this.
        if set(keys) != set(REQUIRED_KEYS):
            return 0, [f"wrong_keys:{keys}"]
    action = obj.get("action")
    conf = obj.get("confidence")
    if action not in ALLOWED_ACTIONS:
        return 0, [f"bad_action:{action}"]
    if conf not in ALLOWED_CONF:
        return 0, [f"bad_confidence:{conf}"]
    # evidence should be string (can be empty)
    if not isinstance(obj.get("evidence"), str):
        return 0, ["evidence_not_string"]
    if not isinstance(obj.get("final"), str):
        return 0, ["final_not_string"]
    return 1, []

def action_match(obj, gold_action):
    if not obj or not isinstance(obj, dict):
        return 0
    return 1 if obj.get("action") == gold_action else 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preds", required=True, help="jsonl with model outputs")
    ap.add_argument("--data", default="data/crab_v0.jsonl", help="crab dataset jsonl")
    args = ap.parse_args()

    # load gold actions
    gold = {}
    with open(args.data, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            gold[item["id"]] = item["gold"]["best_action"]

    total = 0
    strict_json_ok = 0
    schema_ok = 0
    action_ok = 0

    per_cat = {}

    preds_path = Path(args.preds)
    with open(preds_path, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            ex_id = row["id"]
            cat = row.get("category", "unknown")
            total += 1
            per_cat.setdefault(cat, {"n":0, "schema_ok":0, "action_ok":0, "strict_ok":0})
            per_cat[cat]["n"] += 1

            raw = row.get("raw", "")
            obj, strict_ok, parse_err = try_parse_json(raw)
            if strict_ok:
                strict_json_ok += 1
                per_cat[cat]["strict_ok"] += 1

            if obj is None:
                continue

            sc, _ = schema_score(obj)
            schema_ok += sc
            per_cat[cat]["schema_ok"] += sc

            aok = action_match(obj, gold.get(ex_id))
            action_ok += aok
            per_cat[cat]["action_ok"] += aok

    def pct(x): 
        return 0.0 if total == 0 else 100.0 * x / total

    print("=== CRAB SCORE ===")
    print(f"Total: {total}")
    print(f"Strict JSON pass: {strict_json_ok}/{total} ({pct(strict_json_ok):.1f}%)")
    print(f"Schema validity (hard gate): {schema_ok}/{total} ({pct(schema_ok):.1f}%)")
    print(f"Action match: {action_ok}/{total} ({pct(action_ok):.1f}%)")
    print("")
    print("By category:")
    for cat, d in per_cat.items():
        n = d["n"]
        print(f"- {cat:16} n={n:2d} strict={100*d['strict_ok']/n:5.1f}% schema={100*d['schema_ok']/n:5.1f}% action={100*d['action_ok']/n:5.1f}%")

if __name__ == "__main__":
    main()

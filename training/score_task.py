import re

def score_task(task: dict, output: str) -> dict:
    """Score a single task output. Returns a result dict."""
    task_id = task["id"]
    category = task["category"]
    is_adversarial = task.get("adversarial", False)
    pass_patterns = task.get("pass_patterns", [])
    fail_patterns = task.get("fail_patterns", [])

    # Check fail patterns
    fail_matches = []
    for pat in fail_patterns:
        if re.search(pat, output, re.IGNORECASE):
            fail_matches.append(pat)

    if is_adversarial:
        # Adversarial: PASS if NONE of the fail patterns matched
        passed = len(fail_matches) == 0
        reason = "No bad patterns found" if passed else f"Bad patterns matched: {fail_matches}"
    else:
        # Normal: check pass patterns, then ensure no fail patterns
        pass_hits = []
        for pat in pass_patterns:
            if re.search(pat, output, re.IGNORECASE):
                pass_hits.append(pat)

        if fail_matches:
            passed = False
            reason = f"Fail patterns matched: {fail_matches}"
        elif len(pass_hits) >= 1:
            passed = True
            reason = f"Matched {len(pass_hits)}/{len(pass_patterns)} pass patterns"
        else:
            passed = False
            reason = f"No pass patterns matched (0/{len(pass_patterns)})"

    return {
        "id": task_id,
        "category": category,
        "passed": passed,
        "reason": reason,
        "output_length": len(output),
    }

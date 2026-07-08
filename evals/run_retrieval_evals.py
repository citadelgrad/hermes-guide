"""Retrieval evaluation runner for LightRAG."""

import argparse
import base64
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def score_response(case, response):
    """Score a single response against eval case criteria.

    Args:
        case: Eval case dict with id, goal, expected_terms, etc.
        response: Response dict with status, context_lines, recommendations, etc.
                  Can also have a "body" field containing nested fields (fixture format).

    Returns:
        Dict with keys: passed (bool), reason (str)

    Raises:
        KeyError, TypeError for malformed inputs.
    """
    if not isinstance(response, dict):
        raise TypeError(f"response must be dict, got {type(response)}")

    # Support both nested fixture format {"body": {...}} and flat format
    body = response.get("body") or {}
    status = response.get("status")
    context_lines = body.get("context_lines", response.get("context_lines"))
    recommendations = body.get("recommendations", response.get("recommendations"))
    # None means field absent (fall back to text scan); explicit [] means scorer returned empty
    expected_terms_found = response.get("expected_terms_found")
    forbidden_terms_found = response.get("forbidden_terms_found")

    if status is None:
        raise KeyError("response missing required field: status")
    if context_lines is None:
        raise KeyError("response missing required field: context_lines")
    if recommendations is None:
        raise KeyError("response missing required field: recommendations")
    if not isinstance(recommendations, list):
        raise TypeError(f"recommendations must be list, got {type(recommendations)}")

    if status != 200:
        return {"passed": False, "reason": f"status: expected 200, got {status}"}

    # Build recommendations text once for both expected and forbidden fallback scans
    recommendations_text = " ".join(
        rec.get("text", "") if isinstance(rec, dict) else str(rec)
        for rec in recommendations
    ).lower()

    # Check expected_terms — fall back to text scan when field absent
    expected_terms = case.get("expected_terms", [])
    if expected_terms_found is None:
        expected_found = {term.lower() for term in expected_terms if term.lower() in recommendations_text}
    else:
        expected_found = {term.lower() for term in expected_terms_found}

    expected_required = {term.lower() for term in expected_terms}
    if expected_found < expected_required:
        missing = expected_required - expected_found
        return {"passed": False, "reason": f"expected_terms_found: missing {missing}"}

    # Check forbidden_terms — fall back to text scan when field absent
    forbidden_terms = case.get("forbidden_terms", [])
    if forbidden_terms_found is None:
        forbidden_in_text = [term for term in forbidden_terms if term.lower() in recommendations_text]
        if forbidden_in_text:
            return {"passed": False, "reason": f"forbidden_terms_found: {forbidden_in_text} present in text"}
    elif forbidden_terms_found:
        return {"passed": False, "reason": f"forbidden_terms_found: {forbidden_terms_found} present"}

    # Check context_lines
    min_context = case.get("min_context_lines", 10)
    if context_lines < min_context:
        return {"passed": False, "reason": f"context_lines: {context_lines} < {min_context}"}

    return {"passed": True, "reason": "all criteria met"}


LANGFUSE_REQUIRED_ENV = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")


def langfuse_configured():
    """Return True when Langfuse has the credentials needed to submit traces."""
    return all(os.environ.get(name) for name in LANGFUSE_REQUIRED_ENV)


def langfuse_base_url():
    """Return the Langfuse base URL used by the SDK."""
    return os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST") or "https://cloud.langfuse.com"


def default_langfuse_session_id():
    """Stable session id for one eval invocation, visible in Langfuse Sessions."""
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"retrieval-eval-{timestamp}-{uuid.uuid4().hex[:8]}"


def langfuse_session_exists(session_id):
    """Check whether Langfuse can read back the submitted session."""
    credentials = f"{os.environ['LANGFUSE_PUBLIC_KEY']}:{os.environ['LANGFUSE_SECRET_KEY']}"
    auth = base64.b64encode(credentials.encode()).decode()
    req = urllib.request.Request(
        f"{langfuse_base_url().rstrip('/')}/api/public/sessions/{session_id}",
        headers={"Authorization": f"Basic {auth}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise


def wait_for_langfuse_session(session_id, timeout_seconds=20):
    """Poll Langfuse until the session is readable or timeout expires."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        if langfuse_session_exists(session_id):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(2)


def call_query_live(base_url, case, session_id=None):
    """POST a case to the live /query endpoint. Returns response dict with status, body, latency_ms."""
    payload = {
        "goal": case["goal"],
        "skills_list": case.get("skills_list", []),
        "soul_md": case.get("soul_md", ""),
    }
    headers = {"Content-Type": "application/json"}
    if session_id:
        headers["X-Langfuse-Session-Id"] = session_id
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/query",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            latency_ms = int((time.monotonic() - t0) * 1000)
            body = json.loads(resp.read())
            return {"status": resp.status, "body": body, "latency_ms": latency_ms}
    except urllib.error.HTTPError as e:
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {"status": e.code, "latency_ms": latency_ms, "body": {}, "recommendations": [], "context_lines": 0}


def submit_to_langfuse(lf, case, response, result, session_id):
    """Submit eval trace and scores for one case to Langfuse."""
    from langfuse import propagate_attributes

    body = response.get("body", {})
    with propagate_attributes(
        session_id=session_id,
        user_id="retrieval-eval",
        trace_name=f"retrieval-eval:{case['id']}",
        tags=["retrieval-eval", "live"],
        metadata={"case_id": case["id"]},
    ):
        with lf.start_as_current_observation(
            name="retrieval-eval",
            as_type="evaluator",
            input={"goal": case["goal"], "skills_list": case.get("skills_list", []), "case_id": case["id"]},
            output=body,
        ):
            lf.score_current_trace(name="passed", value=1.0 if result["passed"] else 0.0, comment=result["reason"])
            if "latency_ms" in response:
                lf.score_current_trace(name="latency_ms", value=float(response["latency_ms"]))
            if "context_lines" in body:
                lf.score_current_trace(name="context_lines", value=float(body["context_lines"]))


def generate_report(cases, responses):
    """Generate evaluation report from cases and responses."""
    if not isinstance(cases, list):
        raise TypeError(f"cases must be list, got {type(cases)}")
    if not isinstance(responses, list):
        raise TypeError(f"responses must be list, got {type(responses)}")
    if len(cases) != len(responses):
        raise ValueError(f"cases and responses length mismatch: {len(cases)} vs {len(responses)}")

    results = []
    passed_count = 0

    for case, response in zip(cases, responses):
        result = score_response(case, response)
        results.append({
            "case_id": case.get("id"),
            "passed": result["passed"],
            "reason": result["reason"],
        })
        if result["passed"]:
            passed_count += 1

    return {
        "summary": {"total": len(cases), "passed": passed_count, "failed": len(cases) - passed_count},
        "cases": results,
    }


def main():
    """CLI entry point for eval runner."""
    parser = argparse.ArgumentParser(description="Run retrieval evaluation harness")
    parser.add_argument("cases_file", help="Path to eval cases JSONL file")
    parser.add_argument("--url", default=os.environ.get("HERMES_GUIDE_URL", "http://localhost:8000"),
                        help="Base URL for Hermes API")
    parser.add_argument("--report", help="Path to write JSON report")
    parser.add_argument("--fixture", help="Path to fixture responses JSONL (for CI-safe testing)")
    parser.add_argument("--langfuse-session-id", default=os.environ.get("LANGFUSE_SESSION_ID"),
                        help="Langfuse session id for this eval run (default: generated per run)")
    parser.add_argument("--require-langfuse", action="store_true",
                        help="Fail live evals if Langfuse credentials are not configured")
    args = parser.parse_args()
    langfuse_failed = False

    cases_path = Path(args.cases_file)
    if not cases_path.exists():
        print(f"Error: cases file not found: {args.cases_file}", file=sys.stderr)
        sys.exit(1)

    cases = []
    with open(cases_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"Error: malformed JSON in cases file: {e}", file=sys.stderr)
                sys.exit(1)

    if args.fixture:
        # Fixture mode — score static responses, no live calls
        fixture_path = Path(args.fixture)
        if not fixture_path.exists():
            print(f"Error: fixture file not found: {args.fixture}", file=sys.stderr)
            sys.exit(1)
        responses = []
        with open(fixture_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    responses.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"Error: malformed JSON in fixture file: {e}", file=sys.stderr)
                    sys.exit(1)
        if len(responses) != len(cases):
            print(f"Error: fixture has {len(responses)} responses but {len(cases)} cases", file=sys.stderr)
            sys.exit(1)
        lf = None
    else:
        # Live mode — call the real API and submit scores to Langfuse
        lf = None
        langfuse_session_id = args.langfuse_session_id or default_langfuse_session_id()
        if langfuse_configured():
            from langfuse import Langfuse
            lf = Langfuse()
        elif args.require_langfuse:
            missing = ", ".join(name for name in LANGFUSE_REQUIRED_ENV if not os.environ.get(name))
            print(f"Error: Langfuse is required but missing: {missing}", file=sys.stderr)
            sys.exit(1)
        else:
            missing = ", ".join(name for name in LANGFUSE_REQUIRED_ENV if not os.environ.get(name))
            print(f"Langfuse disabled; missing: {missing}", file=sys.stderr)

        print(f"Running {len(cases)} cases against {args.url} ...")
        responses = []
        for case in cases:
            resp = call_query_live(args.url, case, session_id=langfuse_session_id if lf else None)
            responses.append(resp)
            status = "ok" if resp["status"] == 200 else f"HTTP {resp['status']}"
            print(f"  {case['id']}: {status} ({resp.get('latency_ms', '?')}ms)")

        if lf:
            for case, response in zip(cases, responses):
                result = score_response(case, response)
                submit_to_langfuse(lf, case, response, result, session_id=langfuse_session_id)
            lf.flush()
            if wait_for_langfuse_session(langfuse_session_id):
                print(f"Scores submitted to Langfuse session: {langfuse_session_id}")
            else:
                langfuse_failed = True
                print(
                    f"Error: Langfuse did not expose session after flush: {langfuse_session_id}",
                    file=sys.stderr,
                )

    report = generate_report(cases, responses)
    summary = report["summary"]
    print(f"\nEval Results: {summary['passed']}/{summary['total']} passed")

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Report written to: {args.report}")

    sys.exit(0 if summary["failed"] == 0 and not langfuse_failed else 1)


if __name__ == "__main__":
    main()

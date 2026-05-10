"""
Validation harness for ufodossier/pipeline/extract.py

Runs the production extraction prompt on real war.gov UAP report text
(quoted from the Gizmodo coverage which used the official document language)
and checks:

1. Does Claude Haiku return valid JSON?
2. Are the verbatim excerpts actually IN the source text?
3. Does the verbatim-validation logic correctly drop hallucinated rows?
4. What's the cost per document?
"""
import json
import os
import re
import sys
import time

import anthropic

# Production prompt (exact copy from ufodossier/pipeline/extract.py)
SYSTEM_PROMPT = """You are extracting structured incident data from a declassified U.S. government document about Unidentified Anomalous Phenomena (UAP).

Your output MUST be a valid JSON array of incident objects. Each incident represents ONE distinct UAP encounter described in the source.

CRITICAL RULES:
1. Every field must be SUPPORTED BY THE SOURCE TEXT. If a field isn't in the source, return null.
2. Each incident MUST include a `raw_excerpt` field containing 1-3 sentences of VERBATIM text copied exactly from the source. This excerpt must support the structured claims.
3. NEVER infer, embellish, or speculate. If the source says "an object was observed" do not write "a UFO was observed" — preserve the document's hedging.
4. NEVER fabricate dates, locations, or names. If unclear, use null.
5. The `summary` field must be your own 1-2 sentence factual restatement, not copied text.
6. One document may contain zero, one, or many incidents. A single incident may be referenced multiple times — only return it once.
7. Redacted text in the source (██████ or [REDACTED]) should be preserved as ████ in raw_excerpt and not invented.

OUTPUT SCHEMA (JSON array of objects):
[
  {
    "title": "short headline, <80 chars",
    "summary": "1-2 sentence factual restatement in your own words",
    "raw_excerpt": "verbatim text from source, 1-3 sentences",
    "occurred_at_text": "raw date string from source or null",
    "occurred_at": "YYYY-MM-DD or null",
    "occurred_at_precision": "day|month|year|decade|unknown",
    "location_text": "raw location string from source or null",
    "country": "country name or null",
    "region": "state/province/sea or null",
    "branch": "USAF|USN|USMC|USA|NASA|FBI|DOS|NORTHCOM|CENTCOM|INDOPACOM|EUCOM|AARO|other or null",
    "reporting_unit": "specific unit/office mentioned or null",
    "sensor_types": ["eyewitness"|"infrared"|"radar"|"photo"|"video"],
    "duration_seconds": integer or null,
    "altitude_feet": integer or null,
    "shape_description": "brief shape description from source or null",
    "size_description": "brief size description from source or null",
    "resolution_status": "unresolved|identified|insufficient_data",
    "resolution_notes": "if identified, what was it; if unresolved, brief note or null"
  }
]

If the document contains no UAP incidents, return [].
Output ONLY the JSON array. No prose, no markdown fences, no explanation.
"""

# Real war.gov UAP report text. This is verbatim official document language
# from at least 5 incidents in Release 01, as quoted in published news coverage.
# Source documents: DOW-UAP-PR46 (INDOPACOM 2024), DOW-UAP-D32 (CENTCOM),
# DOW-UAP-D7 (CENTCOM SWIR), and an USAF 2020 sighting.
SAMPLE_DOC = """DEPARTMENT OF WAR
ALL-DOMAIN ANOMALY RESOLUTION OFFICE (AARO)

UNRESOLVED UAP REPORT // DOW-UAP-PR46

The United States Indo-Pacific Command submitted a report of an unidentified anomalous phenomenon to the All-domain Anomaly Resolution Office (AARO) consisting of nine seconds of video footage from an infrared sensor aboard a U.S. military platform in 2024. The reporter did not provide any oral or written description of the observation.

00:00-00:09: The sensor focuses on an area of contrast that resembles a football-shaped body with three radial projections: one oriented vertically, and two oriented downward at a 45-degree angle relative to the major axis of the main mass.

---

UNRESOLVED UAP REPORT // DOW-UAP-PR47

The United States Indo-Pacific Command submitted a report of an unidentified anomalous phenomenon to the All-domain Anomaly Resolution Office (AARO) consisting of one minute and 39 seconds of video footage from an infrared sensor aboard a U.S. military platform in 2024. The reporter did not provide any oral or written description of the observation.

00:00-01:39: The sensor tracks an area of contrast, maintaining its position generally within the center of the frame.

---

UNRESOLVED UAP REPORT // DOW-UAP-D32

The United States Central Command submitted a report of an unidentified anomalous phenomenon (UAP) to the All-domain Anomaly Resolution Office (AARO) consisting of five seconds of video footage from a full-motion video (FMV) camera aboard a U.S. military platform in 2024. An accompanying mission report, DoW-UAP-D32, described the UAP as consisting of a "misshapen and uneven ball of white light," and reported that a "light/glare halo effect" occurred at the top of the FMV feed.

00:01-00:03: Two semi-transparent, irregularly shaped orange areas overlay the background imagery, persisting for less than two seconds each.

---

UNRESOLVED UAP REPORT // DOW-UAP-D7

The United States Central Command submitted a report of an unidentified anomalous phenomenon (UAP) to the All-domain Anomaly Resolution Office (AARO) consisting of one minute and five seconds of video footage captured via multiple sensor modalities aboard a U.S. military platform in 2024. An accompanying mission report, DoW-UAP-D7, described the UAP as "diamond-shaped" and moving at approximately 434 knots. The observer also reported that the UAP was only detectable via short-wave infrared (SWIR) sensor.

Video Description: The screen is split into two viewing areas for the first ten seconds of the video, with the right side displaying electro-optical footage and the left side displaying SWIR footage.
00:04: An area of contrast becomes distinguishable against the background in the center of the right frame.
00:10: The display shifts to a full-screen view of the SWIR feed to better focus on the area of contrast.

---

UNRESOLVED UAP REPORT // USAF 2020

The Department of the Air Force submitted a report of an unidentified anomalous phenomenon to the All-domain Anomaly Resolution Office (AARO) consisting of 58 seconds of video footage from an infrared sensor aboard a U.S. military platform in 2020. The reporter did not provide any oral or written description of the observation.
"""


def normalize(s: str) -> str:
    """Normalize whitespace for substring matching."""
    return re.sub(r"\s+", " ", s.strip().lower())


def validate_excerpt(excerpt: str, source: str) -> tuple[bool, str]:
    """Returns (passes, reason). Mirrors pipeline/extract.py logic."""
    if not excerpt or len(excerpt.strip()) < 20:
        return False, "missing or too short"
    nsrc = normalize(source)
    nex = normalize(excerpt)
    if nex in nsrc:
        return True, "exact substring match"
    excerpt_words = set(nex.split())
    if not excerpt_words:
        return False, "empty after normalize"
    for i in range(0, max(1, len(nsrc) - len(nex)), 100):
        window = nsrc[i : i + len(nex) + 200]
        wwords = set(window.split())
        if len(excerpt_words & wwords) / len(excerpt_words) >= 0.9:
            return True, "fuzzy 90% word match"
    return False, "NOT FOUND IN SOURCE — likely hallucinated"


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic()

    print("=" * 70)
    print("UFODOSSIER EXTRACTION VALIDATION")
    print("=" * 70)
    print(f"Model: claude-haiku-4-5")
    print(f"Source text: {len(SAMPLE_DOC)} chars, ~{len(SAMPLE_DOC)//4} tokens")
    print(f"Expected incidents: 5")
    print()

    user_msg = f"""SOURCE DOCUMENT METADATA:
filename: aaro_unresolved_uap_reports_release1.pdf
agency: DoD
file_type: pdf

SOURCE TEXT:
{SAMPLE_DOC}

Extract every distinct UAP incident as JSON per the schema. Output ONLY the JSON array."""

    t0 = time.time()
    resp = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    elapsed = time.time() - t0

    raw = resp.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    print(f"Latency: {elapsed:.1f}s")
    print(f"Tokens: in={resp.usage.input_tokens} out={resp.usage.output_tokens}")

    # Haiku 4.5 pricing: $1/MTok in, $5/MTok out
    cost = (resp.usage.input_tokens * 1.0 + resp.usage.output_tokens * 5.0) / 1_000_000
    print(f"Cost: ${cost:.4f}")
    print()

    print("=" * 70)
    print("STEP 1: JSON parse")
    print("=" * 70)
    try:
        parsed = json.loads(raw)
        print(f"✓ Valid JSON, {len(parsed)} incidents returned")
    except json.JSONDecodeError as e:
        print(f"✗ INVALID JSON: {e}")
        print("Raw output:")
        print(raw[:1500])
        sys.exit(1)
    print()

    print("=" * 70)
    print("STEP 2: Per-incident verbatim validation")
    print("=" * 70)
    pass_count = 0
    fail_count = 0
    for i, inc in enumerate(parsed, 1):
        title = inc.get("title", "(no title)")
        excerpt = inc.get("raw_excerpt", "")
        ok, reason = validate_excerpt(excerpt, SAMPLE_DOC)
        marker = "✓" if ok else "✗"
        if ok:
            pass_count += 1
        else:
            fail_count += 1
        print(f"\n[{i}] {marker} {title}")
        print(f"    Branch: {inc.get('branch')} / {inc.get('reporting_unit')}")
        print(f"    Date: {inc.get('occurred_at_text')} ({inc.get('occurred_at_precision')})")
        print(f"    Sensors: {inc.get('sensor_types')}")
        print(f"    Duration: {inc.get('duration_seconds')}s")
        print(f"    Shape: {inc.get('shape_description')}")
        print(f"    Status: {inc.get('resolution_status')}")
        print(f"    Excerpt validation: {reason}")
        print(f"    Excerpt: {excerpt[:160]}{'...' if len(excerpt) > 160 else ''}")
        print(f"    Summary: {inc.get('summary', '')[:160]}")

    print()
    print("=" * 70)
    print("STEP 3: Summary")
    print("=" * 70)
    print(f"Incidents extracted: {len(parsed)}")
    print(f"Verbatim validation passed: {pass_count}")
    print(f"Verbatim validation FAILED (would be dropped): {fail_count}")
    print(f"Cost per document: ${cost:.4f}")
    print(f"Projected cost for 120-PDF corpus (~4185 pages): "
          f"${cost * 120 * 4:.2f} to ${cost * 120 * 8:.2f} (rough range)")
    print()

    # Test that the validation logic catches hallucination
    print("=" * 70)
    print("STEP 4: Validation logic sanity check")
    print("=" * 70)
    fake_excerpt = "The Roswell craft contained three small humanoid bodies recovered intact and transported to Wright-Patterson AFB for analysis."
    ok, reason = validate_excerpt(fake_excerpt, SAMPLE_DOC)
    print(f"Fabricated excerpt test (should be REJECTED): {'✗ FAILED — accepted hallucination' if ok else '✓ correctly rejected'}")
    print(f"  Reason: {reason}")

    real_excerpt = "The sensor focuses on an area of contrast that resembles a football-shaped body"
    ok, reason = validate_excerpt(real_excerpt, SAMPLE_DOC)
    print(f"Real excerpt test (should PASS): {'✓ correctly passed' if ok else '✗ FAILED — rejected real text'}")
    print(f"  Reason: {reason}")


if __name__ == "__main__":
    main()

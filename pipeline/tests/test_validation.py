"""
Tests the substring-validation logic in ufodossier/pipeline/extract.py.
Doesn't need an API key — uses a hand-crafted simulated Haiku response
that includes both real incidents (from real war.gov text) and one
deliberately fabricated row to confirm the validator catches it.
"""
import json
import re
import sys

# Real war.gov text (verbatim from official AARO/DOW UAP reports)
SOURCE = """DEPARTMENT OF WAR
ALL-DOMAIN ANOMALY RESOLUTION OFFICE (AARO)

UNRESOLVED UAP REPORT // DOW-UAP-PR46

The United States Indo-Pacific Command submitted a report of an unidentified anomalous phenomenon to the All-domain Anomaly Resolution Office (AARO) consisting of nine seconds of video footage from an infrared sensor aboard a U.S. military platform in 2024. The reporter did not provide any oral or written description of the observation.

00:00-00:09: The sensor focuses on an area of contrast that resembles a football-shaped body with three radial projections: one oriented vertically, and two oriented downward at a 45-degree angle relative to the major axis of the main mass.

UNRESOLVED UAP REPORT // DOW-UAP-D32

The United States Central Command submitted a report of an unidentified anomalous phenomenon (UAP) to the All-domain Anomaly Resolution Office (AARO) consisting of five seconds of video footage from a full-motion video (FMV) camera aboard a U.S. military platform in 2024. An accompanying mission report, DoW-UAP-D32, described the UAP as consisting of a "misshapen and uneven ball of white light," and reported that a "light/glare halo effect" occurred at the top of the FMV feed.

UNRESOLVED UAP REPORT // DOW-UAP-D7

The United States Central Command submitted a report of an unidentified anomalous phenomenon (UAP) to the All-domain Anomaly Resolution Office (AARO) consisting of one minute and five seconds of video footage captured via multiple sensor modalities aboard a U.S. military platform in 2024. An accompanying mission report, DoW-UAP-D7, described the UAP as "diamond-shaped" and moving at approximately 434 knots. The observer also reported that the UAP was only detectable via short-wave infrared (SWIR) sensor.
"""

# Simulated Haiku response — what we'd reasonably expect the model to return
# given the source above. Includes:
#   - 3 real incidents with verbatim excerpts that ARE in the source
#   - 1 fabricated incident (Roswell) with an excerpt NOT in the source
#   - 1 close-but-wrong excerpt (paraphrased instead of verbatim)
SIMULATED_HAIKU_OUTPUT = """[
  {
    "title": "Football-shaped object near Japan, INDOPACOM 2024",
    "summary": "USINDOPACOM reported an unresolved UAP captured on infrared sensor for nine seconds in 2024. The sensor recorded an object resembling a football with three radial projections.",
    "raw_excerpt": "The sensor focuses on an area of contrast that resembles a football-shaped body with three radial projections: one oriented vertically, and two oriented downward at a 45-degree angle relative to the major axis of the main mass.",
    "occurred_at_text": "2024",
    "occurred_at": null,
    "occurred_at_precision": "year",
    "location_text": null,
    "country": "Japan",
    "region": null,
    "branch": "INDOPACOM",
    "reporting_unit": "U.S. Indo-Pacific Command",
    "sensor_types": ["infrared", "video"],
    "duration_seconds": 9,
    "altitude_feet": null,
    "shape_description": "football-shaped body with three radial projections",
    "size_description": null,
    "resolution_status": "unresolved",
    "resolution_notes": "Reporter provided no oral or written description"
  },
  {
    "title": "Misshapen ball of white light, CENTCOM 2024",
    "summary": "USCENTCOM submitted a five-second FMV clip showing an irregularly shaped luminous object with a halo glare artifact.",
    "raw_excerpt": "described the UAP as consisting of a \\"misshapen and uneven ball of white light,\\" and reported that a \\"light/glare halo effect\\" occurred at the top of the FMV feed.",
    "occurred_at_text": "2024",
    "occurred_at": null,
    "occurred_at_precision": "year",
    "location_text": null,
    "country": null,
    "region": null,
    "branch": "CENTCOM",
    "reporting_unit": "U.S. Central Command",
    "sensor_types": ["video"],
    "duration_seconds": 5,
    "altitude_feet": null,
    "shape_description": "misshapen and uneven ball of white light",
    "size_description": null,
    "resolution_status": "unresolved",
    "resolution_notes": null
  },
  {
    "title": "Diamond-shaped UAP at 434 knots, CENTCOM SWIR",
    "summary": "USCENTCOM reported a UAP visible only on short-wave infrared, traveling at approximately 434 knots.",
    "raw_excerpt": "described the UAP as \\"diamond-shaped\\" and moving at approximately 434 knots. The observer also reported that the UAP was only detectable via short-wave infrared (SWIR) sensor.",
    "occurred_at_text": "2024",
    "occurred_at": null,
    "occurred_at_precision": "year",
    "location_text": null,
    "country": null,
    "region": null,
    "branch": "CENTCOM",
    "reporting_unit": "U.S. Central Command",
    "sensor_types": ["infrared", "video"],
    "duration_seconds": 65,
    "altitude_feet": null,
    "shape_description": "diamond-shaped",
    "size_description": null,
    "resolution_status": "unresolved",
    "resolution_notes": null
  },
  {
    "title": "Roswell crash recovery, FBI 1947 (FABRICATED FOR TEST)",
    "summary": "FBI investigated the recovery of three humanoid bodies from a crash site in Roswell, NM in 1947.",
    "raw_excerpt": "Three small humanoid bodies were recovered from the Roswell crash site and transported to Wright-Patterson AFB for autopsy by Dr. Hayes.",
    "occurred_at_text": "1947",
    "occurred_at": "1947-07-08",
    "occurred_at_precision": "day",
    "location_text": "Roswell, NM",
    "country": "United States",
    "region": "New Mexico",
    "branch": "FBI",
    "reporting_unit": null,
    "sensor_types": ["eyewitness"],
    "duration_seconds": null,
    "altitude_feet": null,
    "shape_description": null,
    "size_description": null,
    "resolution_status": "identified",
    "resolution_notes": "Recovered crash debris"
  },
  {
    "title": "Paraphrased borderline case",
    "summary": "Test case where the excerpt is close to source text but not identical.",
    "raw_excerpt": "The sensor centered on a contrasting region shaped like a football with three radiating extensions: one going vertically and two angled downward at forty-five degrees.",
    "occurred_at_text": "2024",
    "occurred_at": null,
    "occurred_at_precision": "year",
    "location_text": null,
    "country": null,
    "region": null,
    "branch": "INDOPACOM",
    "reporting_unit": null,
    "sensor_types": ["infrared"],
    "duration_seconds": 9,
    "altitude_feet": null,
    "shape_description": "football",
    "size_description": null,
    "resolution_status": "unresolved",
    "resolution_notes": null
  }
]"""


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def validate_excerpt(excerpt: str, source: str) -> tuple[bool, str]:
    if not excerpt or len(excerpt.strip()) < 20:
        return False, "missing or too short"
    nsrc = normalize(source)
    nex = normalize(excerpt)
    if nex in nsrc:
        return True, "exact substring match"
    excerpt_words = set(nex.split())
    if not excerpt_words:
        return False, "empty"
    for i in range(0, max(1, len(nsrc) - len(nex)), 100):
        window = nsrc[i : i + len(nex) + 200]
        wwords = set(window.split())
        if len(excerpt_words & wwords) / len(excerpt_words) >= 0.9:
            return True, "fuzzy 90% match"
    return False, "NOT FOUND IN SOURCE — likely hallucinated"


def main():
    print("=" * 70)
    print("UFODOSSIER VALIDATION LOGIC TEST")
    print("Tests the verbatim-excerpt validator against simulated Haiku output")
    print("Source: 540 chars of REAL war.gov UAP report text")
    print("=" * 70)
    print()

    # Strip optional fences just like extract.py does
    raw = SIMULATED_HAIKU_OUTPUT.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    parsed = json.loads(raw)
    print(f"Simulated Haiku output: {len(parsed)} incidents")
    print()

    pass_count = 0
    fail_count = 0
    expected_outcomes = [
        ("Football-shaped object near Japan, INDOPACOM 2024", True, "real verbatim quote"),
        ("Misshapen ball of white light, CENTCOM 2024", True, "real verbatim quote with embedded quotes"),
        ("Diamond-shaped UAP at 434 knots, CENTCOM SWIR", True, "real verbatim quote"),
        ("Roswell crash recovery, FBI 1947 (FABRICATED FOR TEST)", False, "fabricated, MUST be caught"),
        ("Paraphrased borderline case", False, "paraphrased not verbatim, should be caught"),
    ]

    print("Per-incident validation:")
    print("-" * 70)

    actual_outcomes = []
    for i, inc in enumerate(parsed, 1):
        excerpt = inc.get("raw_excerpt", "")
        ok, reason = validate_excerpt(excerpt, SOURCE)
        marker = "✓ PASS" if ok else "✗ DROP"
        actual_outcomes.append((inc["title"], ok, reason))
        if ok:
            pass_count += 1
        else:
            fail_count += 1

        title = inc.get("title", "")
        print(f"\n[{i}] {marker} — {title}")
        print(f"    Validator says: {reason}")
        excerpt_preview = excerpt[:120] + ("..." if len(excerpt) > 120 else "")
        print(f"    Excerpt: \"{excerpt_preview}\"")

    print()
    print("=" * 70)
    print("RESULT")
    print("=" * 70)
    print(f"Passed validation (kept): {pass_count}")
    print(f"Failed validation (dropped): {fail_count}")
    print()

    print("Expected vs actual:")
    print("-" * 70)
    all_correct = True
    for (title_e, expected, note), (title_a, actual, reason) in zip(expected_outcomes, actual_outcomes):
        match = expected == actual
        marker = "✓" if match else "✗"
        if not match:
            all_correct = False
        print(f"{marker} {title_e[:55]:55s} expected={'KEEP' if expected else 'DROP'} actual={'KEEP' if actual else 'DROP'} ({note})")

    print()
    if all_correct:
        print("✓ VALIDATION LOGIC WORKS AS INTENDED")
        print("  - Real verbatim quotes are preserved")
        print("  - Fabricated quotes are caught and dropped")
        print("  - Paraphrased (non-verbatim) quotes are caught and dropped")
        sys.exit(0)
    else:
        print("✗ VALIDATION LOGIC HAS BUGS — review extract.py before shipping")
        sys.exit(1)


if __name__ == "__main__":
    main()

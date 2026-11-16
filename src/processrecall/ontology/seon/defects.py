"""Defects in SEON 1.0.5 that the digest cannot resolve from the sources alone.

Each defect is resolved here by name, never by a heuristic in the readers. A defect
the sources show but this table does not list raises :class:`DigestError`, and so
does an entry here that the sources no longer show.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class KnownDefect:
    """A defect in the published sources and how the digest resolves it."""

    key: str
    description: str
    resolution: str


#: The one qualified name SEON 1.0.5 publishes twice.
_FUNCTION = "UFO::Function"

#: Concepts published twice under one qualified name, told apart by their package.
#: The digest keys each one as ``<qualified name>@<package>``.
DUPLICATE_CONCEPTS: Mapping[str, tuple[str, ...]] = {
    _FUNCTION: ("UFO-A", "UFO-C"),
}

#: References to a duplicated name, curated from the definitions. The generalization
#: references are keyed ``(specific concept, general name)``.
AMBIGUOUS_GENERALIZATIONS: Mapping[tuple[str, str], str] = {
    # "Function used to associate a value ... to a Measurable Element": a mathematical
    # function, which is the UFO-A Function (a Set).
    ("COM::Measure", _FUNCTION): f"{_FUNCTION}@UFO-A",
    # "Software Functions are functional dispositions": the UFO-C Function (a Disposition).
    ("RRO::Software Function", _FUNCTION): f"{_FUNCTION}@UFO-C",
}

#: Relation lines printed in the blocks of both duplicates, keyed by the line as
#: published, mapped to the endpoint that owns it.
AMBIGUOUS_RELATION_ENDPOINTS: Mapping[str, str] = {
    # Function Universal is in UFO-C, so its instances are the UFO-C Functions.
    "Function (0..*) instance of (1..*) Function Universal": f"{_FUNCTION}@UFO-C",
}

#: Associations whose verb the pages print with a stray leading backslash
#: (``\creates``). The vendored OWL has the backslash removed; the pages keep it.
BACKSLASH_ASSOCIATIONS: frozenset[str] = frozenset(
    {
        "creates.Software_Measurement_Analysis+Analysis_Result_Description",
        "creates.Software_Measurement_Execution+Measured_Value_Description",
        "intends_to_satisfy.Adaptation_Program+Change_Runtime_Requirement_Artifact",
        "intends_to_satisfy.Compliance_Program+Monitoring_Runtime_Requirement_Artifact",
        "intends_to_satisfy.Program+Requirement_Artifact",
        "intends_to_satisfy.RRT_Program+Runtime_Requirement_Artifact",
        "uses.Software_Measurement_Analysis+Measured_Value_Description",
    }
)

#: Concepts outside UFO whose generalizations never reach a UFO concept. Some have
#: no generalization at all; the rest specialize one of those.
UNGROUNDED_CONCEPTS: frozenset[str] = frozenset(
    {
        "CMPO::Change Request Closing",
        "DPO::Architectural Component",
        "DPO::Architectural Connector",
        "DPO::Architectural Element",
        "EO::Business Role",
        "EO::Employment Type",
        "EO::Formal Organization Member Type",
        "EO::Formal Organization Type",
        "EO::Human Resource Role",
        "EO::OU Assignment",
        "EO::OU Assignment Type",
        "EO::Organizational Unit Type",
        "ROoST::Testing Environment",
        "ROoST::Testing Level",
        "ROoST::Testing Technique Type",
        "RSMO::Data Analysis",
        "RSMO::Data Collection",
        "RSMO::Measurement Plan Item Selection",
        "RSMO::Measurement Result Reporting",
        "RSMO::Periodicity",
        "RSMO::Selection of Data for Analysis",
        "RSMO::Selection of Entity for Measurement",
        "RSMO::Selection of Measurement Goals for Analysis",
        "RSMO::Selection of Measures for Analysis",
        "SPMO::Deliverable",
        "SPMO::Practical Result",
        "SPMO::Work Package",
        "SPO::Software Organization",
    }
)

KNOWN_DEFECTS: tuple[KnownDefect, ...] = (
    KnownDefect(
        key="duplicate-ufo-function",
        description=(
            "UFO publishes two concepts named Function: one in UFO-A specializing Set, "
            "one in UFO-C specializing Disposition. Both print as UFO::Function, and the "
            "generator, which compares concepts by name, prints their one relation in both "
            "blocks and counts it twice in NetworkStats (67 UFO internal relations for 66)."
        ),
        resolution=(
            "Keyed UFO::Function@UFO-A and UFO::Function@UFO-C. COM::Measure specializes "
            "the UFO-A one, RRO::Software Function the UFO-C one, and 'Function instance "
            "of Function Universal' belongs to the UFO-C one, curated from the definitions."
        ),
    ),
    KnownDefect(
        key="backslash-verbs",
        description=(
            "Seven relation verbs carry a stray leading backslash in the Astah model "
            "(e.g. '\\creates'), which the pages print and upstream SEON.owl puts in the IRI."
        ),
        resolution=(
            "Stripped. Whether the backslash was a mistyped derived-relation slash is not "
            "recoverable, so these relations are not marked derived."
        ),
    ),
    KnownDefect(
        key="unnamed-compositions",
        description=(
            "Unnamed composition relations have no verb; the OWL generator invents "
            "'composed_of' for their property IRI."
        ),
        resolution="Predicate null with composition true; the OWL id is kept as the association.",
    ),
    KnownDefect(
        key="ungrounded-concepts",
        description=(
            "28 concepts outside UFO never reach a UFO concept through their generalizations, "
            "although every other one does."
        ),
        resolution="Published as they are; the digest requires exactly these 28 to be ungrounded.",
    ),
    KnownDefect(
        key="lossy-info-csv",
        description="info.csv replaces ';' with ',' and newlines with spaces in definitions.",
        resolution=(
            "Definitions and examples are taken from the pages and checked against info.csv "
            "and the OWL."
        ),
    ),
)

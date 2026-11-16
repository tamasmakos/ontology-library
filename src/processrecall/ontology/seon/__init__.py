"""Digest SEON 1.0.5 into a nested adjacency list.

The OWL is the backbone. ``info.csv`` and the specification pages supply what the
OWL generator threw away. Every join between those sources is total, and a
defect the join cannot resolve on its own is named in
:mod:`processrecall.ontology.seon.defects`. Pinned inputs and provenance live in
``packages/ontology/seon-1.0.5/SOURCE.md``.
"""

from __future__ import annotations


class DigestError(ValueError):
    """The sources disagree, or hold something the digest does not understand."""

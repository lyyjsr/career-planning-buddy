"""In-memory + DB-backed FixtureStore for lazy-record / replay.

One store per Run (constructed in ``TrialRunner._build_executor``). Holds:

* the in-memory ``(sequence,) -> FixtureEntry`` map built up lazily by each
  FixtureXxxProvider method,
* the lazy-recorded bundle that is ready to be persisted once the Run
  completes; for the replay path it is enforced as immutable.

The store is intentionally not thread-safe: provider calls within a Run
are sequential thanks to the cooperative LangGraph executor; cross-Run
sharing is not supported (one store per Run).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from evals.v2.contracts import canonical_sha256

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class FixtureDesyncError(Exception):
    """Raised when a replay call's identity / content drifts from the recorded
    fixture contract.

    Equivalent to issue #1 in the spec: ``fixture_bundle_id`` is the
    Run-level address; once a fixture is frozen, supplying a different
    ``request_projection_hash`` at the same ``sequence`` is desync.
    """

    def __init__(
        self,
        *,
        sequence: int,
        expected: object,
        actual: object,
        reason: str,
    ) -> None:
        self.sequence = sequence
        self.expected = expected
        self.actual = actual
        self.reason = reason
        super().__init__(
            f"fixture desync at sequence {sequence} ({reason}): "
            f"expected={expected!r} actual={actual!r}"
        )


@dataclass(frozen=True, slots=True)
class FixtureEntry:
    """One recorded fixture slot. Immutable once persisted."""

    sequence: int
    provider_kind: str
    provider_method: str
    retry_attempt: int
    request_projection_hash: str
    response_projection: dict[str, object]
    response_projection_hash: str
    fixture_hash: str


@dataclass
class FixtureStore:
    """Per-Run fixture registry. Built lazily by record / replay paths.

    Two operating modes:

    * **record** (first Run for a Trial): ``record(...)`` is called for
      every provider call; entries accumulate; ``finalize_bundle()``
      returns a ``bundle_hash``. ``TrialRunner`` persists the bundle +
      items via ``ProviderCallRepository`` once the Run ends.

    * **replay** (any later Run with the same Trial + bundle): the store
      is preloaded with the bundle's items before the graph runs; every
      ``consume(...)`` validates contract and returns the recorded
      response.
    """

    trial_id: UUID
    session_factory: async_sessionmaker[AsyncSession] | None = None
    bundle_id: UUID | None = None
    entries_by_sequence: dict[int, FixtureEntry] = field(default_factory=dict)
    _frozen: bool = False

    def is_replay(self) -> bool:
        return self._frozen

    # --- record path ---
    def record(
        self,
        *,
        sequence: int,
        provider_kind: str,
        provider_method: str,
        retry_attempt: int,
        request_projection: dict[str, object],
        response_projection: dict[str, object],
    ) -> FixtureEntry:
        if self._frozen:
            raise FixtureDesyncError(
                sequence=sequence,
                expected="record mode",
                actual="replay mode (store already frozen)",
                reason="attempted record after freeze",
            )
        response_hash = canonical_sha256(response_projection)
        request_hash = canonical_sha256(request_projection)
        entry = FixtureEntry(
            sequence=sequence,
            provider_kind=provider_kind,
            provider_method=provider_method,
            retry_attempt=retry_attempt,
            request_projection_hash=request_hash,
            response_projection=response_projection,
            response_projection_hash=response_hash,
            fixture_hash=canonical_sha256({
                "sequence": sequence,
                "provider_kind": provider_kind,
                "provider_method": provider_method,
                "retry_attempt": retry_attempt,
                "request_projection_hash": request_hash,
                "response_projection_hash": response_hash,
            }),
        )
        self.entries_by_sequence[sequence] = entry
        return entry

    def finalize_bundle_hash(self) -> tuple[str, int]:
        """Compute the Bundle hash from all current fixtures.

        Stable ordering by sequence keeps the hash reproducible regardless
        of dict insertion order.
        """

        if not self.entries_by_sequence:
            raise RuntimeError("cannot finalize an empty fixture bundle")
        ordered = [
            self.entries_by_sequence[seq]
            for seq in sorted(self.entries_by_sequence)
        ]
        bundle_hash = canonical_sha256([e.fixture_hash for e in ordered])
        return bundle_hash, len(ordered)

    # --- replay path ---
    def freeze_for_replay(self, entries: list[FixtureEntry]) -> None:
        """Preload the store with recorded entries before the graph runs.

        ``TrialRunner`` reads the existing bundle for the Trial (if any)
        and passes the items here; subsequent ``consume(...)`` calls
        validate and replay.
        """

        if self.entries_by_sequence or self._frozen:
            raise RuntimeError("FixtureStore.freeze_for_replay called twice")
        for entry in entries:
            self.entries_by_sequence[entry.sequence] = entry
        self._frozen = True

    def has_sequence(self, sequence: int) -> bool:
        return sequence in self.entries_by_sequence

    def consume(
        self,
        *,
        sequence: int,
        provider_kind: str,
        provider_method: str,
        retry_attempt: int,
        request_projection: dict[str, object],
    ) -> FixtureEntry:
        """Validate the contract + return the recorded entry."""

        entry = self.entries_by_sequence.get(sequence)
        if entry is None:
            raise FixtureDesyncError(
                sequence=sequence,
                expected="recorded fixture",
                actual=None,
                reason="sequence not present in bundle",
            )
        if entry.provider_kind != provider_kind:
            raise FixtureDesyncError(
                sequence=sequence,
                expected=entry.provider_kind,
                actual=provider_kind,
                reason="provider_kind mismatch",
            )
        if entry.provider_method != provider_method:
            raise FixtureDesyncError(
                sequence=sequence,
                expected=entry.provider_method,
                actual=provider_method,
                reason="provider_method mismatch",
            )
        if entry.retry_attempt != retry_attempt:
            raise FixtureDesyncError(
                sequence=sequence,
                expected=entry.retry_attempt,
                actual=retry_attempt,
                reason="retry_attempt mismatch",
            )
        actual_request_hash = canonical_sha256(request_projection)
        if entry.request_projection_hash != actual_request_hash:
            raise FixtureDesyncError(
                sequence=sequence,
                expected=entry.request_projection_hash,
                actual=actual_request_hash,
                reason="request_projection_hash mismatch",
            )
        return entry


__all__ = [
    "FixtureDesyncError",
    "FixtureEntry",
    "FixtureStore",
]

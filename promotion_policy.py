"""
Promotion Policy (Layer 3 - Cognitive Layer)
==============================================
Implements ADR-012: Diagnosis-Promotion decoupling.

This module consumes a subset of the Diagnostic State produced by the
Bayesian Aggregator (per-evidence world_weights) and independently decides
the pedagogical Stage (fragile / emerging / stable).

It does NOT modify, call, or depend on BayesianAggregator's internal math
(effective_confidence, evidence_factor, concentration_factor). It only
consumes per-evidence world_weights, matching ADR-012 core decision #4.

Design reference: Promotion Policy Design v0.1 (2026-07-15), confirmed by
Yongwu + DeepSeek cross-review (Margin + theta adjustment added 2026-07-15).
Finalized parameters: N=5, K=4, Margin=0.15, theta=0.55

Reset semantics (per Yongwu 2026-07-15 clarification):
  - Cross-Session: do NOT reset. The window must be restored from persisted
    state when a student resumes the same Concept in a later session
    (integration detail: caller is responsible for persisting/loading the
    PromotionPolicy window state alongside dan_state, e.g. via
    dan_memory_service.py; this module itself is storage-agnostic).
  - Cross-Concept: MUST reset. The moment a student moves from Concept A to
    Concept B, the caller must invoke reset() so the new concept's diagnosis
    starts on a clean window, preventing stale dominant_world history from
    one concept leaking into and inflating the Stage of an unrelated concept.
"""

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional, List


UNRESOLVED = "UNRESOLVED"


@dataclass
class PromotionPolicyConfig:
    """Tunable parameters for Promotion Policy. Adjusting these values is
    a parameter-tuning exercise within the ADR-012 architecture and does
    NOT require rewriting the ADR (see ADR-012, final freeze note)."""
    window_size: int = 5        # N: number of most recent evidence rounds considered
    min_consistent: int = 4     # K: minimum consistent dominant_world rounds within
                                 #    window to PROMOTE into stable
    margin: float = 0.15        # Margin: min gap between top-1 and top-2 world weights
                                 #         to accept a dominant_world (else UNRESOLVED)
    theta: float = 0.55         # theta: minimum world_share for the dominant_world to count
    demote_below: int = 3       # Hysteresis latch (added 2026-07-15, Yongwu + DeepSeek):
                                 #    once locked into stable, only demote when the current
                                 #    window's consistency count drops BELOW this value.
                                 #    "宽进严出": promotion uses the strict K threshold;
                                 #    demotion uses this looser, protected threshold to
                                 #    prevent Stable<->Emerging chattering (state chattering).


class PromotionPolicy:
    """
    Stateful, per-student Promotion Policy.

    Usage:
        policy = PromotionPolicy()
        for evidence_event in student_evidence_stream:
            stage = policy.update(world_weights=evidence_event.world_weights)
            # stage in {"fragile", "emerging", "stable"}
    """

    def __init__(self, config: Optional[PromotionPolicyConfig] = None):
        self.config = config or PromotionPolicyConfig()
        self._window: Deque[str] = deque(maxlen=self.config.window_size)
        self._locked_stable: bool = False   # Hysteresis latch state
        self._locked_world: Optional[str] = None  # WHICH world is currently latched;
                                                     # demotion must check THIS world's
                                                     # count, not any world's max count,
                                                     # otherwise the locked world's identity
                                                     # can silently swap (e.g. RWM -> FWM)
                                                     # while Stage stays "stable" the whole
                                                     # time -- a silent misdiagnosis, found
                                                     # during Student C self-check 2026-07-15.

    def _resolve_dominant_world(self, world_weights: Dict[str, float]) -> str:
        """
        Given a dict of world -> weight (e.g. {"RWM": 0.35, "FWM": 0.34, "AWM": 0.31}),
        return the resolved dominant_world for this round, or UNRESOLVED if:
          - the gap between top-1 and top-2 weight is smaller than config.margin, or
          - the top-1 weight itself is below config.theta.
        """
        if not world_weights:
            return UNRESOLVED

        ranked = sorted(world_weights.items(), key=lambda kv: kv[1], reverse=True)
        top_world, top_weight = ranked[0]
        second_weight = ranked[1][1] if len(ranked) > 1 else 0.0

        if (top_weight - second_weight) < self.config.margin:
            return UNRESOLVED
        if top_weight < self.config.theta:
            return UNRESOLVED

        return top_world

    def update(self, world_weights: Dict[str, float]) -> str:
        """
        Feed one new evidence round's world_weights into the policy.
        Returns the current Stage: "fragile" | "emerging" | "stable".
        """
        resolved = self._resolve_dominant_world(world_weights)
        self._window.append(resolved)
        return self._decide_stage()

    def _decide_stage(self) -> str:
        if len(self._window) < self.config.window_size:
            self._locked_stable = False
            self._locked_world = None
            return "fragile"

        # Count consistency per resolved world (UNRESOLVED never counts toward any world)
        counts: Dict[str, int] = {}
        for w in self._window:
            if w == UNRESOLVED:
                continue
            counts[w] = counts.get(w, 0) + 1

        best_world: Optional[str] = None
        best_count = 0
        if counts:
            best_world, best_count = max(counts.items(), key=lambda kv: kv[1])

        # --- Hysteresis latch (宽进严出) ---
        # If already locked into stable, demotion must be checked against the
        # SPECIFIC locked world's own count -- not "whichever world currently has
        # the most votes". Otherwise the locked world's identity can silently
        # swap (e.g. RWM -> FWM) while Stage stays "stable" throughout, which is
        # a silent misdiagnosis rather than a visible chattering problem.
        if self._locked_stable:
            locked_world_count = counts.get(self._locked_world, 0)
            if locked_world_count < self.config.demote_below:
                self._locked_stable = False
                self._locked_world = None
            else:
                return "stable"

        # --- Not locked (either never promoted, or just demoted this round) ---
        if best_count >= self.config.min_consistent:
            self._locked_stable = True
            self._locked_world = best_world
            return "stable"
        if best_count >= 2:
            return "emerging"
        return "fragile"

    def reset(self) -> None:
        """Clear the window and the hysteresis latch.

        MUST be called by the caller when the student switches to a
        different Concept (e.g. 5.4 -> 3.5). MUST NOT be called merely
        because a session ended; cross-session continuity on the same
        Concept must be preserved via persisted state, not a reset.
        """
        self._window.clear()
        self._locked_stable = False
        self._locked_world = None

    @property
    def window_snapshot(self) -> List[str]:
        """Read-only view of current window contents, for debugging/logging."""
        return list(self._window)


# ------------------------------------------------------------------
# Self-check: illustrative simulation only (not a substitute for the
# real validation_runner.py / canonical fixtures in validation/).
# ------------------------------------------------------------------
if __name__ == "__main__":
    policy = PromotionPolicy()

    student_b_rounds = [
        {"RWM": 0.20, "FWM": 0.55, "AWM": 0.25},
        {"RWM": 0.15, "FWM": 0.65, "AWM": 0.20},
        {"RWM": 0.10, "FWM": 0.75, "AWM": 0.15},
        {"RWM": 0.08, "FWM": 0.80, "AWM": 0.12},
        {"RWM": 0.07, "FWM": 0.82, "AWM": 0.11},
        {"RWM": 0.06, "FWM": 0.85, "AWM": 0.09},
        {"RWM": 0.05, "FWM": 0.87, "AWM": 0.08},
    ]
    print("Student B (Flow) simulation:")
    for i, w in enumerate(student_b_rounds, 1):
        stage = policy.update(w)
        print(f"  round {i}: window={policy.window_snapshot} -> stage={stage}")

    policy_d = PromotionPolicy()
    student_d_rounds = [
        {"RWM": 0.35, "FWM": 0.34, "AWM": 0.31},
        {"RWM": 0.33, "FWM": 0.36, "AWM": 0.31},
        {"RWM": 0.34, "FWM": 0.33, "AWM": 0.33},
        {"RWM": 0.36, "FWM": 0.32, "AWM": 0.32},
        {"RWM": 0.32, "FWM": 0.35, "AWM": 0.33},
        {"RWM": 0.34, "FWM": 0.33, "AWM": 0.33},
        {"RWM": 0.35, "FWM": 0.34, "AWM": 0.31},
    ]
    print("\nStudent D (chaotic) simulation:")
    for i, w in enumerate(student_d_rounds, 1):
        stage = policy_d.update(w)
        print(f"  round {i}: window={policy_d.window_snapshot} -> stage={stage}")

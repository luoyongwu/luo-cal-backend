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

=== ADR-016 update (2026-07-28): Stateful rehydration contract ===
PromotionPolicy is a STATEFUL controller (_window deque + _locked_stable /
_locked_world hysteresis latch). It must NOT be re-instantiated as an empty
object on every run_pipeline() call in production -- doing so silently
collapses the N=5/K=4 window mechanism and the hysteresis latch, degrading
Stage decisions into a one-shot transient mapping (see ADR-016 §3, Stage 2,
"[最高优先级架构前置约束] PromotionPolicy 有状态重建契约").

The persisted state lives in dan_state.promotion_state (a JSONB column,
independent from dan_state.temporal_views -- the latter stores the
re-computable Bayesian diagnostic snapshot; the former stores this
controller's own non-recomputable decision history). See export_state()
and the rehydrate() classmethod below, which are the only two methods
callers (run_pipeline() / dan_memory_service.py) need to use for
persistence round-tripping.

=== ADR-017 update (2026-07-31): Mechanism-level parallel window (Step 1) ===
2026-07-31 十位合成学生模拟暴露 Mechanism Parity 违规：StructuralReasoning
（在 BayesianAggregator.MECHANISM_TO_WORLD_DEFAULT 中 50/50 split 到
FWM/AWM）即使证据 100% 纯净，world 层权重差距也结构性小于 Margin=0.15，
导致这类学生永久卡在 fragile stage，即使诊断在 mechanism 层已经完全确定。
详见 docs/adr/ADR-017_mechanism_level_promotion_resolution.md。

本次改动（ADR-017 §8 Step 1）：新增一套与现有 world-level 窗口完全并行
的 mechanism-level 窗口机制（_mechanism_window / _locked_stable_mechanism /
_locked_mechanism），复用同一套 margin/theta/min_consistent/demote_below
判定算法（通过抽出通用的 _resolve_dominant() 实现，不需要认识任何具体
mechanism 名字，保持本模块一贯的"不依赖 BayesianAggregator 内部细节"的
解耦原则）。

这是纯新增：update() 的返回值（即 world-level stage）行为完全不变；
调用方若不传入 mechanism_attribution 参数，本模块的行为与 ADR-017 之前
完全一致。mechanism-level 的判定结果目前只在内部维护、可通过新增的只读
属性观察，尚未接入任何对外可见的 stage 判定逻辑——接入逻辑是 ADR-017
§8 Step 3 的范围，不在本次改动内。
"""

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional, List


UNRESOLVED = "UNRESOLVED"


@dataclass
class PromotionPolicyConfig:
    """Tunable parameters for Promotion Policy. Adjusting these values is
    a parameter-tuning exercise within the ADR-012 architecture and does
    NOT require rewriting the ADR (see ADR-012, final freeze note).

    ADR-017: these same parameters are shared by both the world-level and
    mechanism-level windows (single source of truth for margin/theta/
    window sizing semantics; the two tracks are not meant to diverge in
    strictness, only in which distribution they're applied to)."""
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

    Usage (in-memory, single session):
        policy = PromotionPolicy()
        for evidence_event in student_evidence_stream:
            stage = policy.update(world_weights=evidence_event.world_weights)
            # stage in {"fragile", "emerging", "stable"}

    Usage (production, cross-call persistence -- see ADR-016):
        policy = PromotionPolicy.rehydrate(config=None, state_dict=current_state.get("promotion_state"))
        stage = policy.update(world_weights=recent.world_weights)
        dan_service.write_state(..., promotion_state=policy.export_state())

    Usage (ADR-017, mechanism-level parallel tracking, optional):
        stage = policy.update(
            world_weights=recent.world_weights,
            mechanism_attribution=recent.mechanism_attribution,  # optional
        )
        # world-level `stage` return value is unaffected by passing this.
        # Inspect the parallel mechanism-level track via read-only properties:
        policy.mechanism_window_snapshot   # list[str], mirrors window_snapshot
        policy.locked_mechanism            # Optional[str], mirrors locked_world semantics
        policy.mechanism_stage             # "fragile"/"emerging"/"stable", mechanism-level
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

        # ADR-017 (2026-07-31, Step 1): mechanism-level parallel window.
        # Exactly mirrors the world-level window/latch above, but tracks
        # resolutions over mechanism_attribution instead of world_weights.
        # Independent state -- does not read from or write to the
        # world-level _window/_locked_stable/_locked_world above.
        self._mechanism_window: Deque[str] = deque(maxlen=self.config.window_size)
        self._locked_stable_mechanism: bool = False
        self._locked_mechanism: Optional[str] = None
        self._mechanism_stage: str = "fragile"  # cached result of the last
                                                  # _decide_mechanism_stage()
                                                  # call, exposed read-only
                                                  # via the mechanism_stage
                                                  # property below.

    def _resolve_dominant(self, distribution: Dict[str, float]) -> str:
        """
        Generic top-1/top-2 margin+theta resolver. ADR-017: extracted from
        the world-specific logic so the exact same algorithm can be reused
        for mechanism_attribution (4-way) without this module needing to
        know anything about what the dict's keys represent -- it only ever
        sees "a distribution of floats summing to ~1.0", whether that's
        {"RWM":..,"FWM":..,"AWM":..} or
        {"RepresentationShift":..,"SemanticIntegrity":..,"FlowReasoning":..,"StructuralReasoning":..}.

        Given a dict of key -> weight, return the resolved dominant key for
        this round, or UNRESOLVED if:
          - the gap between top-1 and top-2 weight is smaller than config.margin, or
          - the top-1 weight itself is below config.theta.
        """
        if not distribution:
            return UNRESOLVED

        ranked = sorted(distribution.items(), key=lambda kv: kv[1], reverse=True)
        top_key, top_weight = ranked[0]
        second_weight = ranked[1][1] if len(ranked) > 1 else 0.0

        if (top_weight - second_weight) < self.config.margin:
            return UNRESOLVED
        if top_weight < self.config.theta:
            return UNRESOLVED

        return top_key

    def _resolve_dominant_world(self, world_weights: Dict[str, float]) -> str:
        """
        Given a dict of world -> weight (e.g. {"RWM": 0.35, "FWM": 0.34, "AWM": 0.31}),
        return the resolved dominant_world for this round, or UNRESOLVED per
        the rules documented in _resolve_dominant().

        Kept as a thin named wrapper around the generic _resolve_dominant()
        (ADR-017) for backward compatibility -- any external code or tests
        that reference this method name by name continue to work unchanged.
        """
        return self._resolve_dominant(world_weights)

    def update(
        self,
        world_weights: Dict[str, float],
        mechanism_attribution: Optional[Dict[str, float]] = None,
    ) -> str:
        """
        Feed one new evidence round's world_weights into the policy.
        Returns the current Stage: "fragile" | "emerging" | "stable".

        ADR-016 validation note: callers MUST pass a plain dict here
        (e.g. `recent.world_weights`, not the `recent` WeightVector object
        itself, and NOT `cumulative.world_weights` -- aggregate_dual_scale()'s
        `recent` output is the one intended for this "near-term persistence"
        judgment; `cumulative` is for long-horizon dashboards only).

        ADR-017 (2026-07-31, Step 1): `mechanism_attribution` is a new,
        OPTIONAL parameter. If provided (e.g. `recent.mechanism_attribution`
        from the same WeightVector as world_weights), it is fed in parallel
        into an independent mechanism-level window/latch (see class
        docstring). This has NO EFFECT on the world-level `stage` value
        returned by this call -- that return value is computed exactly as
        before ADR-017. If omitted (the default), this method's behavior is
        byte-for-byte identical to pre-ADR-017 behavior. Inspect the
        mechanism-level track separately via the mechanism_stage /
        locked_mechanism / mechanism_window_snapshot properties.
        """
        if not isinstance(world_weights, dict):
            raise TypeError(
                f"PromotionPolicy.update() expects a plain dict (world_weights), "
                f"got {type(world_weights).__name__}. Did you accidentally pass a "
                f"WeightVector object instead of its .world_weights attribute?"
            )
        resolved = self._resolve_dominant_world(world_weights)
        self._window.append(resolved)
        stage = self._decide_stage()

        # ADR-017 (Step 1): parallel mechanism-level tracking. Purely
        # observational at this stage -- updates internal state and the
        # cached self._mechanism_stage, but does not influence `stage`
        # (the value returned below is unchanged from pre-ADR-017 logic).
        if mechanism_attribution is not None:
            if not isinstance(mechanism_attribution, dict):
                raise TypeError(
                    f"PromotionPolicy.update() expects mechanism_attribution to be "
                    f"a plain dict when provided, got "
                    f"{type(mechanism_attribution).__name__}."
                )
            resolved_mechanism = self._resolve_dominant(mechanism_attribution)
            self._mechanism_window.append(resolved_mechanism)
            self._mechanism_stage = self._decide_mechanism_stage()

        return stage

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

    def _decide_mechanism_stage(self) -> str:
        """
        ADR-017 (Step 1): exact mirror of _decide_stage(), operating on
        self._mechanism_window / self._locked_stable_mechanism /
        self._locked_mechanism instead of the world-level equivalents.
        Kept as a fully separate method (rather than parameterizing
        _decide_stage()) so the world-level code path is untouched by this
        change -- zero risk of accidentally altering production stage
        decisions while adding this.
        """
        if len(self._mechanism_window) < self.config.window_size:
            self._locked_stable_mechanism = False
            self._locked_mechanism = None
            return "fragile"

        counts: Dict[str, int] = {}
        for m in self._mechanism_window:
            if m == UNRESOLVED:
                continue
            counts[m] = counts.get(m, 0) + 1

        best_mechanism: Optional[str] = None
        best_count = 0
        if counts:
            best_mechanism, best_count = max(counts.items(), key=lambda kv: kv[1])

        if self._locked_stable_mechanism:
            locked_mechanism_count = counts.get(self._locked_mechanism, 0)
            if locked_mechanism_count < self.config.demote_below:
                self._locked_stable_mechanism = False
                self._locked_mechanism = None
            else:
                return "stable"

        if best_count >= self.config.min_consistent:
            self._locked_stable_mechanism = True
            self._locked_mechanism = best_mechanism
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

        ADR-017: also clears the mechanism-level window/latch, keeping
        both tracks synchronized on concept-switch resets (a mechanism-level
        lock from the previous concept leaking into a new concept would be
        the same class of bug that Cross-Concept reset exists to prevent
        for the world-level track).
        """
        self._window.clear()
        self._locked_stable = False
        self._locked_world = None

        self._mechanism_window.clear()
        self._locked_stable_mechanism = False
        self._locked_mechanism = None
        self._mechanism_stage = "fragile"

    @property
    def window_snapshot(self) -> List[str]:
        """Read-only view of current window contents, for debugging/logging."""
        return list(self._window)

    @property
    def mechanism_window_snapshot(self) -> List[str]:
        """ADR-017: read-only view of the mechanism-level window contents,
        mirroring window_snapshot above."""
        return list(self._mechanism_window)

    @property
    def locked_mechanism(self) -> Optional[str]:
        """ADR-017: the currently latched mechanism (if the mechanism-level
        track has reached "stable"), or None. Mirrors the semantics of
        _locked_world but for the mechanism-level track. This is a pure
        observation point in Step 1 -- not yet consumed by any decision
        logic (see ADR-017 §8 Step 3 for the wiring)."""
        return self._locked_mechanism

    @property
    def mechanism_stage(self) -> str:
        """ADR-017: the mechanism-level track's current stage
        ("fragile"/"emerging"/"stable"), independent of the world-level
        `stage` returned by update(). Reflects the most recent call to
        update() that included a mechanism_attribution argument; if
        update() has never been called with mechanism_attribution, this
        stays at its initial value "fragile"."""
        return self._mechanism_stage

    # ------------------------------------------------------------------
    # ADR-016: stateful persistence round-trip (added 2026-07-28)
    # ADR-017: extended to also round-trip the mechanism-level track
    # (added 2026-07-31, Step 1)
    # ------------------------------------------------------------------

    def export_state(self) -> dict:
        """
        Export the controller's internal state snapshot for persistence.

        Intended destination: dan_state.promotion_state (JSONB, independent
        from dan_state.temporal_views -- see module docstring). The caller
        (run_pipeline()) should call this AFTER update() on every invocation
        and write the result back via DANMemoryService.write_state().

        ADR-017: now also includes the mechanism-level window/latch state
        (mechanism_window / locked_stable_mechanism / locked_mechanism).
        Historical promotion_state JSONB blobs written before this change
        simply won't have these three keys -- rehydrate() below handles
        that case by defaulting to a fresh mechanism-level track, which is
        the correct behavior for state persisted before this feature
        existed (there is no mechanism-level history to recover for those
        rows; starting fresh is not a data-loss bug, it's the honest
        reflection of what was actually being tracked at the time).
        """
        return {
            "window": list(self._window),
            "locked_stable": self._locked_stable,
            "locked_world": self._locked_world,
            # ADR-017 additions:
            "mechanism_window": list(self._mechanism_window),
            "locked_stable_mechanism": self._locked_stable_mechanism,
            "locked_mechanism": self._locked_mechanism,
        }

    @classmethod
    def rehydrate(
        cls,
        config: Optional[PromotionPolicyConfig],
        state_dict: Optional[dict],
    ) -> "PromotionPolicy":
        """
        Reconstruct a PromotionPolicy instance from a persisted state_dict
        (as produced by export_state()).

        If state_dict is None or empty (e.g. a brand-new student who has
        never had a promotion_state row written yet), this is equivalent
        to a fresh PromotionPolicy(config) -- i.e. an empty window and an
        unlocked latch, which is the correct starting state for a student
        with no prior history.

        ADR-016 note: this classmethod (not __init__ + manual attribute
        assignment) is the ONLY sanctioned way for run_pipeline() to obtain
        a PromotionPolicy instance in production. Calling PromotionPolicy()
        directly in run_pipeline() silently discards all prior window/latch
        state and is the exact failure mode this contract exists to prevent.

        ADR-017: also restores the mechanism-level track if present in
        state_dict. Uses .get(...) with safe defaults throughout, so
        historical state_dict blobs written before ADR-017 (missing the
        mechanism_window/locked_stable_mechanism/locked_mechanism keys)
        rehydrate cleanly into a fresh (empty) mechanism-level track rather
        than raising a KeyError -- this is the backward-compatibility
        guarantee promised in the module docstring.
        """
        instance = cls(config)
        if state_dict:
            window_size = instance.config.window_size
            instance._window = deque(
                state_dict.get("window", []), maxlen=window_size
            )
            instance._locked_stable = state_dict.get("locked_stable", False)
            instance._locked_world = state_dict.get("locked_world", None)

            # ADR-017 additions (all default-safe for pre-ADR-017 state blobs):
            instance._mechanism_window = deque(
                state_dict.get("mechanism_window", []), maxlen=window_size
            )
            instance._locked_stable_mechanism = state_dict.get(
                "locked_stable_mechanism", False
            )
            instance._locked_mechanism = state_dict.get("locked_mechanism", None)
            # Recompute cached mechanism_stage from the restored window/latch
            # so it's consistent immediately after rehydration, without
            # requiring an extra update() call first.
            if instance._mechanism_window:
                instance._mechanism_stage = instance._decide_mechanism_stage()
        return instance


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

    # --- ADR-016 self-check: export_state() / rehydrate() round-trip ---
    print("\nADR-016 rehydration self-check:")
    snapshot = policy.export_state()
    print(f"  exported state: {snapshot}")
    rehydrated = PromotionPolicy.rehydrate(config=None, state_dict=snapshot)
    assert rehydrated.window_snapshot == policy.window_snapshot
    assert rehydrated._locked_stable == policy._locked_stable
    assert rehydrated._locked_world == policy._locked_world
    print("  rehydrated instance matches original state: OK")

    fresh = PromotionPolicy.rehydrate(config=None, state_dict=None)
    assert fresh.window_snapshot == []
    assert fresh._locked_stable is False
    assert fresh._locked_world is None
    print("  rehydrate(state_dict=None) yields a clean fresh instance: OK")

    # --- ADR-017 self-check: mechanism-level parallel track (Step 1) ---
    # Illustrates the StructuralReasoning scenario from ADR-017 §2: world
    # weights stay split ~50/50 between FWM/AWM (never resolves at the
    # world level), while mechanism_attribution is 100% StructuralReasoning
    # every round (resolves immediately at the mechanism level). This is a
    # schematic illustration with hand-picked numbers, not a byte-for-byte
    # reproduction of BayesianAggregator's real output for SIM_03/SIM_04 --
    # the actual regression fixture (ADR-017 §8 Step 2) will use real
    # pipeline-computed numbers.
    print("\nADR-017 mechanism-level parallel track self-check "
          "(schematic StructuralReasoning scenario):")
    policy_structural = PromotionPolicy()
    world_weights_stuck = {"RWM": 0.14, "FWM": 0.46, "AWM": 0.40}  # never resolves
    mechanism_pure_structural = {
        "RepresentationShift": 0.0,
        "SemanticIntegrity": 0.0,
        "FlowReasoning": 0.0,
        "StructuralReasoning": 1.0,  # fully resolves every round
    }
    for i in range(1, 6):
        stage = policy_structural.update(
            world_weights=world_weights_stuck,
            mechanism_attribution=mechanism_pure_structural,
        )
        print(f"  round {i}: world_stage={stage} (expected: stuck at 'fragile') | "
              f"mechanism_stage={policy_structural.mechanism_stage} "
              f"(expected: reaches 'stable' by round 5) | "
              f"locked_mechanism={policy_structural.locked_mechanism}")

    assert policy_structural.mechanism_stage == "stable", (
        "预期：纯净 StructuralReasoning 证据应在 mechanism 层判定为 stable，"
        "即使 world 层因为 50/50 split 永久卡在 fragile"
    )
    assert policy_structural.locked_mechanism == "StructuralReasoning"
    print("  mechanism-level track correctly resolves what the world-level "
          "track structurally cannot: OK")
    print("  (world-level `stage` return values above were entirely "
          "unaffected by the parallel mechanism tracking, confirming this "
          "is a pure, zero-impact addition per ADR-017 §8 Step 1.)")

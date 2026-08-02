"""
test_promotion_policy_rehydrate.py

PromotionPolicy.rehydrate() 向后兼容性回归测试。

纯本地测试，不需要 Supabase、不需要网络、不需要任何外部凭证——
promotion_policy.py 本身零外部依赖（见其模块文档："It does NOT modify,
call, or depend on BayesianAggregator's internal math"），这份测试也
延续同样的原则，可以在任何环境下直接 `python3 validation/
test_promotion_policy_rehydrate.py` 运行，几秒内出结果。

背景（ADR-017 §8 Step 3）：export_state()/rehydrate() 新增了三个
mechanism-level 字段（mechanism_window/locked_stable_mechanism/
locked_mechanism）。设计承诺是"历史 promotion_state JSONB 数据（ADR-017
之前写入、不含这三个新字段）rehydrate 时应该优雅降级为全新的
mechanism-level track，不应该报错"。本测试把这个承诺固化为可重复验证
的断言。

运行方式：直接执行本文件（`if __name__ == "__main__"` 会跑全部场景并
在任何一个断言失败时以非零退出码终止），或作为 pytest 用例导入
（每个 test_* 函数都可以被 pytest 独立发现和运行）。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from promotion_policy import PromotionPolicy


def test_rehydrate_with_none_state_dict():
    """全新学生（从未有过 promotion_state 记录）应该得到完全干净的初始状态，
    包括 mechanism-level track。"""
    p = PromotionPolicy.rehydrate(config=None, state_dict=None)
    assert p.mechanism_window_snapshot == []
    assert p.locked_mechanism is None
    assert p.mechanism_stage == "fragile"


def test_rehydrate_with_legacy_state_missing_mechanism_fields():
    """历史 promotion_state（ADR-017 之前写入，只有 window/locked_stable/
    locked_world 三个旧字段，完全没有 mechanism_window/
    locked_stable_mechanism/locked_mechanism 这三个 ADR-017 新增字段）
    必须能正常 rehydrate，不抛 KeyError，world-level 状态正确恢复，
    mechanism-level 优雅降级为全新状态。"""
    legacy_state = {
        "window": ["RWM", "RWM", "RWM", "RWM"],
        "locked_stable": False,
        "locked_world": None,
        # 故意不包含 mechanism_window / locked_stable_mechanism / locked_mechanism
    }
    p = PromotionPolicy.rehydrate(config=None, state_dict=legacy_state)

    # world-level 应该正确恢复历史数据
    assert p.window_snapshot == ["RWM", "RWM", "RWM", "RWM"]

    # mechanism-level（历史数据里不存在）应该优雅降级，不报错
    assert p.mechanism_window_snapshot == []
    assert p.locked_mechanism is None
    assert p.mechanism_stage == "fragile"


def test_legacy_student_can_continue_after_rehydrate():
    """历史学生 rehydrate 后应该能正常继续接收新证据，world-level window
    正确延续（不因为 rehydrate 而被清空重置），mechanism-level track 从
    这一刻起正常开始累积。"""
    legacy_state = {
        "window": ["RWM", "RWM", "RWM", "RWM"],
        "locked_stable": False,
        "locked_world": None,
    }
    p = PromotionPolicy.rehydrate(config=None, state_dict=legacy_state)

    stage = p.update(
        world_weights={"RWM": 0.9, "FWM": 0.07, "AWM": 0.03},
        mechanism_attribution={
            "RepresentationShift": 0.9, "SemanticIntegrity": 0.05,
            "FlowReasoning": 0.03, "StructuralReasoning": 0.02,
        },
    )

    # 第5轮证据加入后，world window应该正确延续到5个元素（不是从0重新开始）
    assert p.window_snapshot == ["RWM", "RWM", "RWM", "RWM", "RWM"]
    assert stage == "stable"  # 5轮里4轮以上RWM，应该晋升


def test_export_rehydrate_round_trip_with_new_fields():
    """新写入的 promotion_state（包含 ADR-017 三个新字段）export 后
    rehydrate 回来，mechanism-level track 应该完整还原，不丢失信息。"""
    p1 = PromotionPolicy()
    for _ in range(5):
        p1.update(
            world_weights={"RWM": 0.8, "FWM": 0.15, "AWM": 0.05},
            mechanism_attribution={
                "RepresentationShift": 0.8, "SemanticIntegrity": 0.1,
                "FlowReasoning": 0.07, "StructuralReasoning": 0.03,
            },
        )
    snapshot = p1.export_state()

    assert "mechanism_window" in snapshot
    assert "locked_stable_mechanism" in snapshot
    assert "locked_mechanism" in snapshot

    p2 = PromotionPolicy.rehydrate(config=None, state_dict=snapshot)
    assert p2.mechanism_window_snapshot == p1.mechanism_window_snapshot
    assert p2.locked_mechanism == p1.locked_mechanism
    assert p2.mechanism_stage == p1.mechanism_stage


def run_all():
    tests = [
        test_rehydrate_with_none_state_dict,
        test_rehydrate_with_legacy_state_missing_mechanism_fields,
        test_legacy_student_can_continue_after_rehydrate,
        test_export_rehydrate_round_trip_with_new_fields,
    ]
    failed = []
    for t in tests:
        try:
            t()
            print(f"✅ {t.__name__}")
        except AssertionError as e:
            print(f"❌ {t.__name__}: {e}")
            failed.append(t.__name__)
        except Exception as e:
            print(f"❌ {t.__name__}: 意外异常 {type(e).__name__}: {e}")
            failed.append(t.__name__)

    print()
    if failed:
        print(f"❌ {len(failed)}/{len(tests)} 个测试失败: {failed}")
        sys.exit(1)
    else:
        print(f"✅ 全部 {len(tests)} 个测试通过")
        sys.exit(0)


if __name__ == "__main__":
    run_all()

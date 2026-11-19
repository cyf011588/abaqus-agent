# -*- coding: utf-8 -*-
"""测试：对话式建模的意图匹配 + 通用建模知识 fallback。"""
from agent import modeling_knowledge as mk
from agent import tools


def test_match_case():
    assert mk.match_case("建一个三层钢框架")[0][0] == "steel_frame"
    assert mk.match_case("带圆孔方板拉伸")[0][0] == "plate_hole"
    assert mk.match_case("平面三角桁架")[0][0] == "truss"
    assert mk.match_case("量子点") == []


def test_plan_model_hit():
    out = tools.plan_model("建一个钢框架")
    assert "steel_frame" in out
    assert "必问参数" in out


def test_plan_model_miss():
    out = tools.plan_model("一个完全没见过的结构")
    assert "fallback" in out


def test_modeling_guide_sections():
    assert "C3D8R" in mk.guide_section("单元")
    assert "屈服应力" in mk.guide_section("材料")
    assert "从零建模流程" in mk.guide_section("流程")


def test_modeling_guide_tool():
    assert "S4R" in tools.modeling_guide("薄壁")

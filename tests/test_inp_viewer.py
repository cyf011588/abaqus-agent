# -*- coding: utf-8 -*-
"""inp 解析器单元测试（全 mock，不依赖 Abaqus 与外部项目）。"""
from agent.inp_viewer import parse_inp, rotation_matrix, _apply


def test_parse_non_numeric_element_line():
    """数据段混入非数字行（如 nset/set 名称）不应崩溃，跳过即可。"""
    text = (
        "*Node\n"
        "1, 0., 0., 0.\n"
        "2, 1., 0., 0.\n"
        "*Element, type=B31\n"
        "1, 1, 2\n"
        "\tbolt-111-lin-1-2.3\n"   # 模拟混入的非数字行
    )
    d = parse_inp(text)
    assert d["summary"]["nodes"] == 2
    assert d["summary"]["line_segs"] >= 1


def test_shell_s4r_triangulation():
    text = """*Part, name=P
*Node
1, 0., 0., 0.
2, 1., 0., 0.
3, 1., 1., 0.
4, 0., 1., 0.
*Element, type=S4R
1, 1, 2, 3, 4
*End Part
*Assembly, name=Assembly
*Instance, name=P-1, part=P
0., 0., 0.
*End Instance
*End Assembly
"""
    d = parse_inp(text)
    assert d["summary"]["nodes"] == 4
    assert d["summary"]["shell_tris"] == 2
    assert d["summary"]["solid_tris"] == 0
    assert d["summary"]["line_segs"] == 0


def test_solid_external_surface_culling():
    # 两个六面体共享一个面：外表面 = 6+6-2 = 10 面 = 20 三角
    text = """*Part, name=P
*Node
1, 0., 0., 0.
2, 1., 0., 0.
3, 1., 1., 0.
4, 0., 1., 0.
5, 0., 0., 1.
6, 1., 0., 1.
7, 1., 1., 1.
8, 0., 1., 1.
9, 0., 0., 2.
10, 1., 0., 2.
11, 1., 1., 2.
12, 0., 1., 2.
*Element, type=C3D8R
1, 1, 2, 3, 4, 5, 6, 7, 8
2, 5, 6, 7, 8, 9, 10, 11, 12
*End Part
*Assembly, name=Assembly
*Instance, name=P-1, part=P
0., 0., 0.
*End Instance
*End Assembly
"""
    d = parse_inp(text)
    assert d["summary"]["nodes"] == 12
    assert d["summary"]["solid_tris"] == 20
    assert d["summary"]["shell_tris"] == 0


def test_line_elements():
    text = """*Part, name=P
*Node
1, 0., 0., 0.
2, 1., 0., 0.
3, 0., 0., 1.
*Element, type=B31
1, 1, 2
*Element, type=SpringA, elset=x1-spring
2, 1, 3
*End Part
*Assembly, name=Assembly
*Instance, name=P-1, part=P
0., 0., 0.
*End Instance
*End Assembly
"""
    d = parse_inp(text)
    assert d["summary"]["line_segs"] == 2


def test_rotation_matrix_z90():
    R = rotation_matrix((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 90.0)
    x, y, z = _apply((1.0, 0.0, 0.0), R, (0.0, 0.0, 0.0))
    assert abs(x) < 1e-9 and abs(y - 1.0) < 1e-9 and abs(z) < 1e-9


def test_instance_translation():
    text = """*Part, name=P
*Node
1, 0., 0., 0.
2, 1., 0., 0.
3, 1., 1., 0.
4, 0., 1., 0.
*Element, type=S4R
1, 1, 2, 3, 4
*End Part
*Assembly, name=Assembly
*Instance, name=P-1, part=P
10., 20., 30.
*End Instance
*End Assembly
"""
    d = parse_inp(text)
    # 节点 1 平移后应为 (10, 20, 30)
    assert abs(d["nodes"][0] - 10.0) < 1e-9
    assert abs(d["nodes"][1] - 20.0) < 1e-9
    assert abs(d["nodes"][2] - 30.0) < 1e-9


def test_parse_inp_file_smoke(tmp_path):
    """真实文件往返：写最小 inp，parse_inp_file 能读。"""
    from agent.inp_viewer import parse_inp_file
    p = tmp_path / "m.inp"
    p.write_text("""*Part, name=P
*Node
1, 0., 0., 0.
2, 1., 0., 0.
3, 1., 1., 0.
*Element, type=S3
1, 1, 2, 3
*End Part
*Assembly, name=Assembly
*Instance, name=P-1, part=P
0., 0., 0.
*End Instance
*End Assembly
""", encoding="utf-8")
    d = parse_inp_file(str(p))
    assert d["summary"]["shell_tris"] == 1


def test_flat_inp_no_part():
    """无 *Part/*Assembly 的扁平手写 inp（内置案例库输出）。"""
    text = """*Heading
** flat
*Node
1, 0, 0, 0
2, 1, 0, 0
3, 1, 1, 0
4, 0, 1, 0
*Element, type=S4R
1, 1, 2, 3, 4
*Nset, nset=ALL
1, 2, 3, 4
*Elset, elset=EALL
1
*Step, name=L
*Static
1., 1., 1e-05, 1.
*Node Output
U
*Element Output
S
*End Step
"""
    d = parse_inp(text)
    assert d["summary"]["nodes"] == 4
    assert d["summary"]["shell_tris"] == 2
    assert d["summary"]["parts"] == []  # 顶层无 Part 名

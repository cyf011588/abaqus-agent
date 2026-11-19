# -*- coding: utf-8 -*-
"""inpkit 网格生成测试。"""
from agent.inpkit import (NodeTable, hex_mesh, shell_rect_mesh, plate_hole_mesh,
                          l_bracket_mesh, beam_mesh, truss_mesh, annulus_quarter_mesh,
                          frame_mesh)


def test_hex_mesh_counts():
    nodes, elems, nsets = hex_mesh(100, 10, 10, 20, 2, 2)
    assert len(nodes) == 189
    assert len(elems) == 80
    assert len(nsets["X0"]) == 9  # (ny+1)*(nz+1)
    assert len(nsets["X1"]) == 9
    for _, conn in elems:
        assert len(conn) == 8
        assert all(1 <= n <= 189 for n in conn)


def test_hex_mesh_bounds():
    nodes, _, _ = hex_mesh(100, 10, 10, 20, 2, 2)
    xs = [x for _, x, _, _ in nodes]
    ys = [y for _, _, y, _ in nodes]
    zs = [z for _, _, _, z in nodes]
    assert min(xs) == 0 and max(xs) == 100
    assert min(ys) == 0 and max(ys) == 10
    assert min(zs) == 0 and max(zs) == 10


def test_shell_rect_mesh():
    nodes, elems, _ = shell_rect_mesh(200, 100, 20, 10)
    assert len(nodes) == 21 * 11
    assert len(elems) == 200


def test_plate_hole_mesh_counts():
    nodes, elems, nsets = plate_hole_mesh(200, 100, 20, 12, 48)
    assert len(nodes) == 13 * 48
    assert len(elems) == 12 * 48
    assert nsets["LEFT"] and nsets["RIGHT"]


def test_plate_hole_outer_boundary():
    nodes, _, _ = plate_hole_mesh(200, 100, 20, 12, 48)
    xs = [x for _, x, _, _ in nodes]
    ys = [y for _, _, y, _ in nodes]
    assert max(xs) <= 100.0 + 1e-6
    assert max(ys) <= 50.0 + 1e-6


def test_l_bracket_shared_edge_dedup():
    nodes, elems, nsets = l_bracket_mesh(100, 100, 20, 4, 20, 16)
    assert len(nodes) == 185  # 竖直 105 + 水平 85 - 共享边 5
    assert len(elems) == 144  # 竖直 80 + 水平 64
    assert len(nsets["FIXED"]) == 5
    assert len(nsets["TIP"]) == 5


def test_nodetable_dedup():
    nt = NodeTable()
    a = nt.add(1.0, 2.0, 0.0)
    b = nt.add(1.0, 2.0, 0.0)
    c = nt.add(1.0, 2.0, 3.0)
    assert a == b
    assert c != a
    assert len(nt.nodes) == 2


def test_beam_mesh():
    nodes, elems, nsets = beam_mesh(1000, 20)
    assert len(nodes) == 21
    assert len(elems) == 20
    assert nsets["LEFT"] == [1]
    assert nsets["RIGHT"] == [21]
    assert nsets["MID"] == [11]


def test_truss_mesh():
    nodes, elems, nsets = truss_mesh(1000, 500)
    assert len(nodes) == 3
    assert len(elems) == 3
    assert nsets["C"] == [3]


def test_annulus_quarter_mesh():
    nodes, elems, nsets = annulus_quarter_mesh(100, 200, 8, 12)
    assert len(nodes) == 9 * 13  # (nr+1)*(nt+1)
    assert len(elems) == 8 * 12
    assert len(nsets["INNER"]) == 13
    assert len(nsets["SYMX"]) == 9


def test_frame_mesh():
    nodes, elems, nsets = frame_mesh(2, 2, 3000, 6000)
    assert len(nodes) == 3 * 3  # (n_story+1)*(n_bay+1)
    n_cols = 2 * 3
    n_beams = 2 * 2
    assert len(elems) == n_cols + n_beams
    assert len(nsets["BASE"]) == 3
    assert len(nsets["FLOORS"]) == 2 * 3

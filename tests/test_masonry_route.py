"""API: /api/masonry/<calc> and the page."""
import json

from concretedesignpy.webapp.app import create_app

FENCE = dict(H_mm=2400, L_m=30, t_nom_mm=200, t_spec_mm=190, unit_density_kN_m3=16.5, grout="solid",
             plastered_faces=2, fm_MPa=10, fy_MPa=275, mortar="S", special_inspection=True, zone=4, Ca=0.44,
             V_kph=258.4, exposure="B", Kzt=1.0, wind_zone="body", method="SD", bar_db_mm=12, bar_s_mm=400,
             footing=dict(B_mm=1200, D_mm=300, Df_mm=900, soil_class=4, gamma_c_kN_m3=23.6))


def _client():
    return create_app().test_client()


def test_page_and_nav():
    c = _client()
    r = c.get("/calculator/masonry")
    assert r.status_code == 200 and b"/api/masonry/" in r.data
    assert b"CHB Walls" in c.get("/").data


def test_fence_route_ok_and_json_safe():
    r = _client().post("/api/masonry/fence", json=FENCE)
    assert r.status_code == 200
    body = json.loads(r.data)            # strict JSON: no Infinity/NaN
    assert body["status"] == "success" and body["result"]["ok"] is True
    assert body["result"]["report"]["lines"]


def test_route_errors():
    c = _client()
    bad = dict(FENCE)
    bad.pop("special_inspection")
    r = c.post("/api/masonry/fence", json=bad)
    assert r.status_code == 400 and "special_inspection" in r.get_json()["message"]
    assert c.post("/api/masonry/nope", json={}).status_code == 404
    assert c.post("/api/masonry/fence", data="x", content_type="text/plain").status_code == 400
    r = c.post("/api/masonry/fence", json=dict(FENCE, footing=dict(FENCE["footing"], B_mm=200)))
    assert r.status_code == 400 or json.loads(r.data)["status"] == "success"   # B < 300 mm → Table 304-1 ValueError

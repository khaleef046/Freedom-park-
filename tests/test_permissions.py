from app.models.user import User, Role


def test_anonymous_redirected_from_admin(client):
    res = client.get("/admin/dashboard", follow_redirects=False)
    assert res.status_code == 302
    assert "/auth/staff-login" in res.location


def test_staff_partner_cannot_access_admin_dashboard(client):
    # Login as staff partner
    client.post("/auth/staff-login", data={
        "username": "test_partner",
        "password": "pass123"
    })
    # Attempting to access admin dashboard should be forbidden (403)
    res = client.get("/admin/dashboard")
    assert res.status_code == 403


def test_security_cannot_access_admin_pricing(client):
    # Login as security
    client.post("/auth/staff-login", data={
        "username": "test_security",
        "password": "pass123"
    })
    res = client.get("/admin/pricing")
    assert res.status_code == 403


def test_content_staff_cannot_access_settings(client):
    # Login as content staff
    client.post("/auth/staff-login", data={
        "username": "test_content",
        "password": "pass123"
    })
    res = client.get("/admin/settings")
    assert res.status_code == 403


def test_super_admin_has_full_access(client):
    # Login as super admin
    client.post("/auth/staff-login", data={
        "username": "test_superadmin",
        "password": "pass123"
    })
    res = client.get("/admin/dashboard")
    assert res.status_code == 200

    res_audit = client.get("/admin/audit-logs")
    assert res_audit.status_code == 200

from app.adapters.cloud_identity import deployment_headers, request_oidc


def test_request_token_takes_priority_and_does_not_leak_between_requests(monkeypatch):
    monkeypatch.setenv("VERCEL_OIDC_TOKEN", "development-token")
    first = request_oidc.set("request-one")
    try:
        assert deployment_headers() == {"x-vercel-trusted-oidc-idp-token": "request-one"}
        second = request_oidc.set("request-two")
        try:
            assert deployment_headers()["x-vercel-trusted-oidc-idp-token"] == "request-two"
        finally:
            request_oidc.reset(second)
        assert deployment_headers()["x-vercel-trusted-oidc-idp-token"] == "request-one"
    finally:
        request_oidc.reset(first)
    assert deployment_headers()["x-vercel-trusted-oidc-idp-token"] == "development-token"


def test_rotated_file_is_read_each_time(tmp_path, monkeypatch):
    file = tmp_path / "oidc"
    monkeypatch.setenv("VERCEL_OIDC_TOKEN_FILE", str(file))
    file.write_text("first")
    assert deployment_headers()["x-vercel-trusted-oidc-idp-token"] == "first"
    file.write_text("second")
    assert deployment_headers()["x-vercel-trusted-oidc-idp-token"] == "second"

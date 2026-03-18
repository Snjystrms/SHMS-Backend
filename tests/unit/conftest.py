import pytest


@pytest.fixture(autouse=True)
def _clear_dependency_overrides(request):
    """
    Ensure FastAPI dependency overrides don't leak between tests.

    We intentionally don't import `app.main` here because importing the full app
    pulls in all routers (including ones that import numpy), which can crash the
    interpreter on some macOS setups.
    """
    yield
    app = getattr(request.node, "_fastapi_app_under_test", None)
    if app is not None:
        app.dependency_overrides.clear()


import os
import pytest
from contextvars import copy_context
from umelogging.context import (
    set_context,
    update_context,
    get_context,
    with_request_id,
    _stable_hash,
    app_var,
    env_var,
    service_var,
    component_var,
    request_id_var,
    user_hash_var,
    extra_var,
)


@pytest.fixture(autouse=True)
def reset_context():
    """Reset all context variables before each test."""
    app_var.set(os.getenv("UME_APP"))
    env_var.set(os.getenv("UME_ENV", "prod"))
    service_var.set(os.getenv("UME_SERVICE"))
    component_var.set("")
    request_id_var.set("")
    user_hash_var.set("")
    extra_var.set(None)
    yield


class TestSetContext:
    def test_set_app(self):
        set_context(app="myapp")
        assert app_var.get() == "myapp"

    def test_set_env(self):
        set_context(env="staging")
        assert env_var.get() == "staging"

    def test_set_service(self):
        set_context(service="api-gateway")
        assert service_var.get() == "api-gateway"

    def test_set_component(self):
        set_context(component="auth")
        assert component_var.get() == "auth"

    def test_set_request_id(self):
        set_context(request_id="req-123")
        assert request_id_var.get() == "req-123"

    def test_set_user_id_hashes_value(self):
        set_context(user_id="user@example.com")
        hashed = user_hash_var.get()
        assert hashed != "user@example.com"
        assert len(hashed) == 32  # truncated sha256

    def test_set_extra(self):
        set_context(extra={"foo": "bar"})
        assert extra_var.get() == {"foo": "bar"}

    def test_set_extra_merges(self):
        set_context(extra={"foo": "bar"})
        set_context(extra={"baz": "qux"})
        assert extra_var.get() == {"foo": "bar", "baz": "qux"}

    def test_set_multiple_fields(self):
        set_context(app="app1", env="dev", service="svc1")
        assert app_var.get() == "app1"
        assert env_var.get() == "dev"
        assert service_var.get() == "svc1"

    def test_none_values_not_set(self):
        set_context(app="original")
        set_context(app=None, env="newenv")
        assert app_var.get() == "original"
        assert env_var.get() == "newenv"


class TestUpdateContext:
    def test_update_is_alias_for_set(self):
        update_context(app="updated-app")
        assert app_var.get() == "updated-app"


class TestGetContext:
    def test_returns_all_fields(self):
        set_context(
            app="testapp",
            env="test",
            service="testsvc",
            component="testcomp",
            request_id="req-456",
        )
        ctx = get_context()
        assert ctx["app"] == "testapp"
        assert ctx["env"] == "test"
        assert ctx["service"] == "testsvc"
        assert ctx["component"] == "testcomp"
        assert ctx["request_id"] == "req-456"

    def test_user_hash_wrapped_in_dict(self):
        set_context(user_id="testuser")
        ctx = get_context()
        assert "user" in ctx
        assert "hash" in ctx["user"]
        assert len(ctx["user"]["hash"]) == 32

    def test_user_none_when_not_set(self):
        ctx = get_context()
        assert ctx["user"] is None

    def test_extra_fields_merged_into_context(self):
        set_context(extra={"custom_field": "custom_value"})
        ctx = get_context()
        assert ctx["custom_field"] == "custom_value"


class TestWithRequestId:
    def test_generates_uuid_when_none_provided(self):
        rid = with_request_id()
        assert len(rid) == 36  # UUID format
        assert request_id_var.get() == rid

    def test_uses_provided_id(self):
        rid = with_request_id("custom-request-id")
        assert rid == "custom-request-id"
        assert request_id_var.get() == "custom-request-id"


class TestStableHash:
    def test_consistent_hash(self):
        hash1 = _stable_hash("user123")
        hash2 = _stable_hash("user123")
        assert hash1 == hash2

    def test_different_inputs_different_hashes(self):
        hash1 = _stable_hash("user1")
        hash2 = _stable_hash("user2")
        assert hash1 != hash2

    def test_hash_length(self):
        result = _stable_hash("anyuser")
        assert len(result) == 32

    def test_salt_affects_hash(self, monkeypatch):
        hash1 = _stable_hash("user")
        monkeypatch.setenv("UME_USER_HASH_SALT", "different_salt")
        # Need to reimport to pick up new env value
        from umelogging import context
        hash2 = context._stable_hash("user")
        assert hash1 != hash2


class TestContextIsolation:
    def test_context_isolated_between_copies(self):
        """Test that contextvars properly isolate between context copies."""
        set_context(app="parent")

        def child_task():
            set_context(app="child")
            return app_var.get()

        ctx = copy_context()
        child_result = ctx.run(child_task)

        assert child_result == "child"
        assert app_var.get() == "parent"  # Parent unchanged

    def test_extra_not_shared_between_contexts(self):
        """Verify the mutable default fix - extra should not leak between contexts."""
        set_context(extra={"ctx1": "value1"})

        def other_context():
            # In a fresh context, extra should be None, not the parent's dict
            extra_var.set(None)
            set_context(extra={"ctx2": "value2"})
            return extra_var.get()

        ctx = copy_context()
        other_extra = ctx.run(other_context)

        assert other_extra == {"ctx2": "value2"}
        assert "ctx2" not in (extra_var.get() or {})

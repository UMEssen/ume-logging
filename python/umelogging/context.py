# Purpose: Context variables (app/env/service/component/request_id/user_id) with helpers

import contextvars, os, uuid, hashlib
from typing import Optional, Dict

app_var = contextvars.ContextVar("ume_app", default=os.getenv("UME_APP"))
env_var = contextvars.ContextVar("ume_env", default=os.getenv("UME_ENV", "prod"))
service_var = contextvars.ContextVar("ume_service", default=os.getenv("UME_SERVICE"))
component_var = contextvars.ContextVar("ume_component", default="")
request_id_var = contextvars.ContextVar("ume_request_id", default="")
user_hash_var = contextvars.ContextVar("ume_user_hash", default="")
extra_var = contextvars.ContextVar("ume_extra", default=None)

def set_context(*, app: Optional[str]=None, env: Optional[str]=None,
                service: Optional[str]=None, component: Optional[str]=None,
                request_id: Optional[str]=None, user_id: Optional[str]=None,
                extra: Optional[Dict]=None) -> None:
    if app is not None: app_var.set(app)
    if env is not None: env_var.set(env)
    if service is not None: service_var.set(service)
    if component is not None: component_var.set(component)
    if request_id is not None: request_id_var.set(request_id)
    if user_id is not None:
        user_hash_var.set(_stable_hash(user_id))
    if extra: extra_var.set({**(extra_var.get() or {}), **extra})

def update_context(**kwargs) -> None:
    set_context(**kwargs)

def get_context() -> Dict:
    return {
        "app": app_var.get(),
        "env": env_var.get(),
        "service": service_var.get(),
        "component": component_var.get(),
        "request_id": request_id_var.get(),
        "user": {"hash": user_hash_var.get()} if user_hash_var.get() else None,
        **(extra_var.get() or {}),
    }

def with_request_id(req_id: Optional[str]=None) -> str:
    rid = req_id or str(uuid.uuid4())
    request_id_var.set(rid)
    return rid

def _stable_hash(s: str) -> str:
    # Purpose: anonymize user identifiers consistently
    salt = os.getenv("UME_USER_HASH_SALT", "ume")
    return hashlib.sha256((salt + ":" + s).encode()).hexdigest()[:32]
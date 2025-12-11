# app/monitoring/context.py
"""
Context helpers using contextvars for request/tenant/flow propagation.
"""
import contextvars

request_id_var = contextvars.ContextVar("request_id", default=None)
tenant_id_var = contextvars.ContextVar("tenant_id", default=None)
flow_id_var = contextvars.ContextVar("flow_id", default=None)

def set_request_context(request_id=None, tenant_id=None, flow_id=None):
    if request_id is not None:
        request_id_var.set(request_id)
    if tenant_id is not None:
        tenant_id_var.set(tenant_id)
    if flow_id is not None:
        flow_id_var.set(flow_id)

def get_request_context():
    return {
        "request_id": request_id_var.get(),
        "tenant_id": tenant_id_var.get(),
        "flow_id": flow_id_var.get(),
    }

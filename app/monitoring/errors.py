from app.db.session import SessionLocal
from app.db.repositories.error_repository import ErrorRepository
from app.monitoring.logger import log
from app.monitoring.slack_alerts import send_slack_alert
import traceback


async def record_error(component: str, function: str, message: str, details: dict = None, stacktrace: str = None, request_id: str = None, tenant_id: str = None, flow_id: str = None, severity: str = "ERROR", alert: bool = True):
    try:
        async with SessionLocal() as db:
            repo = ErrorRepository(db)
            await repo.create(
                request_id=request_id,
                tenant_id=tenant_id,
                flow_id=flow_id,
                component=component,
                function=function,
                severity=severity,
                message=message,
                details=details,
                stacktrace=stacktrace,
            )
    except Exception as e:
        log("ERROR", f"Failed to persist ErrorLog: {e}", component="errors", request_id=request_id, tenant_id=tenant_id, flow_id=flow_id)
    # Always log
    log(severity, message, component=component, request_id=request_id, tenant_id=tenant_id, flow_id=flow_id, details=details)
    if alert and severity in ("ERROR", "CRITICAL"):
        try:
            await send_slack_alert(message=message, context={"details": details}, severity=severity, module=component, request_id=request_id)
        except Exception as e:
            log("ERROR", f"Failed to send Slack alert for error: {e}", component="errors", request_id=request_id)

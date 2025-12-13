# Health Endpoints

The application exposes these health and readiness endpoints (from OpenAPI):

- **GET `/admin/health`**: Shallow health endpoint. Returns basic service status.
  - Summary: "Health"
  - Description: "Shallow health endpoint."

- **GET `/admin/health/deep`**: Deep health endpoint. Performs DB connectivity and file provider checks across tenants.
  - Summary: "Health Deep"
  - Description: "Deep health endpoint performing database connectivity and file provider checks."

- **GET `/admin/ready`**: Alias for deep readiness to match deployment health checks.
  - Summary: "Ready"
  - Description: "Alias for deep readiness to match deployment health checks."

Use these endpoints in health probes. Example:

```bash
curl -sS http://127.0.0.1:8000/admin/health
curl -sS http://127.0.0.1:8000/admin/health/deep
curl -sS http://127.0.0.1:8000/admin/ready
```

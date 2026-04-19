from __future__ import annotations

import argparse
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from job_hunter.dashboard_service import DashboardService

# This server serves the dashboard static files and provides APIs for health check, resume metadata retrieval, and resume tailoring.
class DashboardRequestHandler(SimpleHTTPRequestHandler):
    def __init__(
        self,
        *args,
        directory: str,
        service: DashboardService,
        **kwargs,
    ) -> None:
        self.service = service
        super().__init__(*args, directory=directory, **kwargs)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._add_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json(self.service.health())
            return
        if parsed.path == "/api/resume":
            self._send_json(self.service.get_resume_metadata())
            return
        self.path = parsed.path
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/tailor-resume":
            self.send_error(404, "Unknown API endpoint")
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(body.decode("utf-8"))
            job_id = str(payload.get("job_id", "")).strip()
            if not job_id:
                raise ValueError("job_id is required")
            result = self.service.tailor_resume(job_id)
        except KeyError as exc:
            self._send_json({"error": str(exc)}, status=404)
            return
        except (FileNotFoundError, ValueError) as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)
            return

        self._send_json(result, status=200)

    def _add_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._add_cors_headers()
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve the job dashboard with resume APIs.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--profile", default="config/profile.json")
    parser.add_argument("--database-dir", default="database")
    parser.add_argument("--dashboard-dir", default="dashboard")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    port = int(os.environ.get("PORT", args.port))
    host = "0.0.0.0" if os.environ.get("PORT") else args.host
    workspace_dir = Path(__file__).resolve().parent
    service = DashboardService(
        profile_path=workspace_dir / args.profile,
        database_dir=workspace_dir / args.database_dir,
        dashboard_dir=workspace_dir / args.dashboard_dir,
        workspace_dir=workspace_dir,
    )
    handler = partial(
        DashboardRequestHandler,
        directory=str(service.dashboard_dir),
        service=service,
    )
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Dashboard server running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


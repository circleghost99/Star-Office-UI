"""Port scanning service for security monitoring."""

import subprocess
import threading
from datetime import datetime

_scan_timer = None
_scan_lock = threading.Lock()

COMMON_PORTS = {
    21: ("FTP", "medium"),
    22: ("SSH", "medium"),
    23: ("Telnet", "high"),
    25: ("SMTP", "medium"),
    53: ("DNS", "low"),
    80: ("HTTP", "low"),
    110: ("POP3", "medium"),
    143: ("IMAP", "medium"),
    443: ("HTTPS", "low"),
    445: ("SMB", "high"),
    993: ("IMAPS", "low"),
    995: ("POP3S", "low"),
    1433: ("MSSQL", "high"),
    1521: ("Oracle", "high"),
    3306: ("MySQL", "high"),
    3389: ("RDP", "high"),
    5432: ("PostgreSQL", "high"),
    5900: ("VNC", "high"),
    6379: ("Redis", "high"),
    8080: ("HTTP-Alt", "low"),
    8443: ("HTTPS-Alt", "low"),
    9090: ("Proxy", "medium"),
    9200: ("Elasticsearch", "high"),
    11211: ("Memcached", "high"),
    27017: ("MongoDB", "high"),
}


def scan_port(port):
    """Check if a port is open on localhost."""
    try:
        result = subprocess.run(
            ["nc", "-z", "-w", "1", "127.0.0.1", str(port)],
            capture_output=True,
            timeout=3,
        )
        return "open" if result.returncode == 0 else "closed"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "filtered"


def run_scan():
    """Run a full port scan and store results."""
    from database import get_db

    now = datetime.now().isoformat()
    db = get_db()

    for port, (service, risk) in COMMON_PORTS.items():
        status = scan_port(port)
        if status == "open":
            db.execute(
                "INSERT INTO port_scan_results (port, service, status, risk_level, scanned_at) VALUES (?, ?, ?, ?, ?)",
                (port, service, status, risk, now),
            )

    db.commit()
    _schedule_next()


def _schedule_next():
    """Schedule the next scan based on settings."""
    global _scan_timer
    from database import get_db

    try:
        db = get_db()
        row = db.execute("SELECT port_scan_enabled, port_scan_interval_hours FROM security_settings WHERE id = 1").fetchone()
        if not row or not row["port_scan_enabled"]:
            return
        interval = max(1, row["port_scan_interval_hours"]) * 3600
    except Exception:
        interval = 6 * 3600

    with _scan_lock:
        if _scan_timer:
            _scan_timer.cancel()
        _scan_timer = threading.Timer(interval, run_scan)
        _scan_timer.daemon = True
        _scan_timer.start()


def reschedule_scanner():
    """Cancel current timer and reschedule based on current settings."""
    _schedule_next()


def start_scanner():
    """Start the port scanner on server startup."""
    _schedule_next()

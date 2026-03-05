"""Service manager module for interacting with systemd services via systemctl.

Only services explicitly listed in the ``ALLOWED_SERVICES`` environment
variable (comma-separated list of ``<name>.service`` units) can be queried or
controlled.  All subprocess calls use a list of arguments rather than
``shell=True`` to prevent injection, and service names are validated against a
strict regex before being passed to ``systemctl``.

Required setup
--------------
1. Set ``ALLOWED_SERVICES`` in your ``.env`` file, e.g.::

       ALLOWED_SERVICES=myapp.service,another.service

2. Grant the bot user passwordless ``sudo`` for the exact ``systemctl``
   verbs it needs.  Create ``/etc/sudoers.d/telegram-assistant``::

       botuser ALL=(ALL) NOPASSWD: \\
           /bin/systemctl start *, \\
           /bin/systemctl stop *, \\
           /bin/systemctl restart *

   Replace ``botuser`` with the OS user that runs the assistant process and
   ``/bin/systemctl`` with the actual path returned by ``which systemctl``.
   Use ``visudo -c`` to verify the file after creation.

   Note: The software-level allowlist (``ALLOWED_SERVICES``) is the
   primary security gate; the sudoers rule only needs to permit the
   three control verbs so it can remain relatively broad.  The bot
   will refuse any service not on the allowlist regardless of what
   the sudoers rule says.
"""

import os
import re
import subprocess

from utils.logging import get_logger

logger = get_logger(__name__)

# Pattern that a valid systemd unit name must match before we ever pass it to a
# subprocess call.  Allows letters, digits, hyphens, underscores, dots, and the
# @ character (for template units), and requires the .service suffix.
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-_@.]*\.service$")

# Subprocess timeout (seconds) for non-blocking status queries.
_STATUS_TIMEOUT = 10
# Subprocess timeout (seconds) for start/stop/restart – these may take longer.
_CONTROL_TIMEOUT = 30


def _get_allowed_services() -> list[str]:
    """Return the allowlist from the ``ALLOWED_SERVICES`` environment variable.

    Each entry is stripped of surrounding whitespace.  Empty strings are
    discarded.  The caller is responsible for normalising names before
    comparing against this list.
    """
    raw = os.environ.get("ALLOWED_SERVICES", "")
    return [s.strip() for s in raw.split(",") if s.strip()]


def _normalise(service: str) -> str:
    """Append ``.service`` suffix if the caller omitted it."""
    service = service.strip()
    if not service.endswith(".service"):
        service = service + ".service"
    return service


def _validate(service: str) -> str:
    """Validate *service* and return the normalised name.

    Raises :class:`ValueError` when the name fails the regex check or is not
    on the allowlist.
    """
    service = _normalise(service)

    if not _SAFE_NAME_RE.match(service):
        raise ValueError(
            f"Invalid service name '{service}'. "
            "Names must start with an alphanumeric character and may only "
            "contain letters, digits, hyphens, underscores, dots, and '@', "
            "and must end with '.service'."
        )

    allowed = _get_allowed_services()
    if not allowed:
        raise ValueError(
            "No services are configured. "
            "Set the ALLOWED_SERVICES environment variable."
        )

    if service not in allowed:
        raise ValueError(
            f"Service '{service}' is not in the allowed services list. "
            f"Allowed: {', '.join(allowed)}"
        )

    return service


def _run(args: list[str], timeout: int = _STATUS_TIMEOUT) -> tuple[int, str]:
    """Run *args* as a subprocess and return ``(returncode, combined_output)``."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
        return result.returncode, output
    except subprocess.TimeoutExpired:
        logger.warning("systemctl command timed out: %s", args)
        return 1, "Command timed out."
    except FileNotFoundError:
        logger.error("systemctl not found; is systemd running on this host?")
        return 1, "systemctl not found. Is systemd installed?"


# ---------------------------------------------------------------------------
# Public API – these functions are exposed as agent tools
# ---------------------------------------------------------------------------


def list_services() -> list[dict]:
    """List all allowed services together with their current active state.

    Returns a list of dicts, each with ``service`` and ``state`` keys.
    The ``state`` value is the output of ``systemctl is-active`` (e.g.
    ``active``, ``inactive``, ``failed``).
    """
    allowed = _get_allowed_services()
    if not allowed:
        return [{"error": "No services configured. Set ALLOWED_SERVICES."}]

    results = []
    for svc in allowed:
        code, output = _run(["systemctl", "is-active", svc], timeout=_STATUS_TIMEOUT)
        results.append({"service": svc, "state": output})

    return results


def get_service_status(service: str) -> dict:
    """Return detailed status information for *service*.

    Queries ``systemctl show`` for the properties
    ``ActiveState``, ``SubState``, ``LoadState``, and ``Description``.

    Args:
        service: The unit name (with or without the ``.service`` suffix).

    Returns:
        A dict with ``service``, ``active_state``, ``sub_state``,
        ``load_state``, and ``description`` keys, or an ``error`` key on
        failure.
    """
    try:
        service = _validate(service)
    except ValueError as exc:
        return {"error": str(exc)}

    code, output = _run(
        [
            "systemctl",
            "show",
            service,
            "--no-pager",
            "--property=ActiveState,SubState,LoadState,Description",
        ],
        timeout=_STATUS_TIMEOUT,
    )

    if code != 0:
        return {"service": service, "error": output or "Failed to query service status."}

    props: dict[str, str] = {}
    for line in output.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            props[key.strip()] = value.strip()

    return {
        "service": service,
        "active_state": props.get("ActiveState", "unknown"),
        "sub_state": props.get("SubState", "unknown"),
        "load_state": props.get("LoadState", "unknown"),
        "description": props.get("Description", ""),
    }


def start_service(service: str) -> str:
    """Start *service*.

    Requires the bot process user to have passwordless sudo rights for
    ``systemctl start <service>``.

    Args:
        service: The unit name (with or without the ``.service`` suffix).

    Returns:
        A confirmation message on success, or an error message string.
    """
    try:
        service = _validate(service)
    except ValueError as exc:
        return str(exc)

    logger.info("Starting service %s", service)
    code, output = _run(["sudo", "systemctl", "start", service], timeout=_CONTROL_TIMEOUT)
    if code != 0:
        return f"Failed to start '{service}': {output}"
    return f"Service '{service}' started successfully."


def stop_service(service: str) -> str:
    """Stop *service*.

    Requires the bot process user to have passwordless sudo rights for
    ``systemctl stop <service>``.

    Args:
        service: The unit name (with or without the ``.service`` suffix).

    Returns:
        A confirmation message on success, or an error message string.
    """
    try:
        service = _validate(service)
    except ValueError as exc:
        return str(exc)

    logger.info("Stopping service %s", service)
    code, output = _run(["sudo", "systemctl", "stop", service], timeout=_CONTROL_TIMEOUT)
    if code != 0:
        return f"Failed to stop '{service}': {output}"
    return f"Service '{service}' stopped successfully."


def restart_service(service: str) -> str:
    """Restart *service*.

    Requires the bot process user to have passwordless sudo rights for
    ``systemctl restart <service>``.

    Args:
        service: The unit name (with or without the ``.service`` suffix).

    Returns:
        A confirmation message on success, or an error message string.
    """
    try:
        service = _validate(service)
    except ValueError as exc:
        return str(exc)

    logger.info("Restarting service %s", service)
    code, output = _run(["sudo", "systemctl", "restart", service], timeout=_CONTROL_TIMEOUT)
    if code != 0:
        return f"Failed to restart '{service}': {output}"
    return f"Service '{service}' restarted successfully."

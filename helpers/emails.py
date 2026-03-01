from __future__ import annotations
import re
import asyncio
from typing import Optional, TYPE_CHECKING
from pathlib import Path

import resend
from resend.emails import _emails

from jinja2 import Environment, FileSystemLoader

if TYPE_CHECKING:
    from core import SbugaFastAPI

_jinja_env = Environment(
    loader=FileSystemLoader(Path("email_templates")),
    autoescape=True,
)

# RFC 5321 compliant email regex
# NOTE: re2 doesn't support lookahead. using re here
_EMAIL_RE = re.compile(
    r"(?:[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+)*"
    r'|"(?:[!#$%&\'*+/=?^_`{|}~\-\x20-\x7E]|\\[!#$%&\'*+/=?^_`{|}~\-\x20-\x7E])*")'
    r"@(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?"
)


def check_email(email: str) -> bool:
    return bool(_EMAIL_RE.fullmatch(email))


def get_base_email(email: str) -> str:
    local, domain = email.lower().split("@", 1)
    local = local.split("+")[0]
    return f"{local}@{domain}"


def render_email_template(template_name: str, **kwargs) -> str:
    return _jinja_env.get_template(template_name).render(**kwargs)


async def send_email(
    params: _emails.Emails.SendParams,
    options: Optional[_emails.Emails.SendOptions] = None,
) -> _emails.Emails.SendResponse:
    return await asyncio.to_thread(resend.Emails.send, params, options)


# SPECIFIC EMAILS
async def send_verification_email(
    app: SbugaFastAPI, to_email: str, display_name: str, username: str, token: str
) -> None:
    verify_url = (
        f"https://{app.config.server.frontend_domain}/verify_email?token={token}"
        if app.config.server.environment == "production"
        else f"{app.base_url}/accounts/email/verify?token={token}"
    )
    html = render_email_template(
        "email_verify.jinja2",
        display_name=display_name,
        username=username,
        verify_url=verify_url,
    )
    text = render_email_template(
        "email_verify_text.jinja2",
        display_name=display_name,
        username=username,
        verify_url=verify_url,
    )

    return await send_email(
        {
            "from": f"accounts@{app.config.resend.email_domain}",
            "to": to_email,
            "subject": "Verify your email",
            "html": html,
            "text": text,
        }
    )

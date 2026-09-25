# ============================================================
# EMAIL_SERVICE.PY
# Envio de e-mails transacionais do SpyTeam
# ============================================================

import html
import os

import resend


def _app_url() -> str:
    return os.getenv(
        "APP_URL",
        "http://127.0.0.1:8000"
    ).rstrip("/")


def criar_link_recuperacao(token: str) -> str:
    return (
        f"{_app_url()}/redefinir-senha"
        f"?token={token}"
    )


def criar_link_verificacao_email(token: str) -> str:
    return (
        f"{_app_url()}/verificar-email"
        f"?token={token}"
    )


def _config_email() -> tuple[str, str, str]:
    modo = os.getenv(
        "EMAIL_MODE",
        "resend"
    ).strip().lower()

    api_key = os.getenv(
        "RESEND_API_KEY",
        ""
    ).strip()

    remetente = os.getenv(
        "EMAIL_FROM",
        ""
    ).strip()

    if modo != "console":
        if not api_key:
            raise RuntimeError(
                "RESEND_API_KEY não configurado."
            )

        if not remetente:
            raise RuntimeError(
                "EMAIL_FROM não configurado."
            )

    return modo, api_key, remetente


def _enviar_resend(
    destinatario: str,
    assunto: str,
    corpo_html: str,
    *,
    api_key: str,
    remetente: str
) -> None:
    resend.api_key = api_key

    try:
        resposta = resend.Emails.send({
            "from": remetente,
            "to": [destinatario],
            "subject": assunto,
            "html": corpo_html,
        })

        if not resposta:
            raise RuntimeError(
                "O Resend não retornou confirmação do envio."
            )

    except Exception as erro:
        raise RuntimeError(
            "Falha ao enviar e-mail pelo Resend: "
            f"{erro}"
        ) from erro


def enviar_email_recuperacao(
    destinatario: str,
    token: str
) -> None:
    """Envia o link de recuperação de senha."""

    link = criar_link_recuperacao(token)
    modo, api_key, remetente = _config_email()

    if modo == "console":
        print(
            "[SpyTeam] Link de recuperação para",
            destinatario,
            ":",
            link
        )
        return

    destinatario_html = html.escape(destinatario)
    link_html = html.escape(link, quote=True)

    corpo_html = f"""
    <div style="
        font-family:Arial,sans-serif;
        max-width:560px;
        margin:auto;
        color:#101828
    ">
        <h2 style="color:#3161CA">
            Redefinição de senha - SPY TEAM
        </h2>

        <p>
            Recebemos uma solicitação para redefinir
            a senha da conta associada a
            <strong>{destinatario_html}</strong>.
        </p>

        <p>
            Use o botão abaixo para criar uma nova senha.
            O link expira em 15 minutos.
        </p>

        <p style="margin:28px 0">
            <a
                href="{link_html}"
                style="
                    background:#3161CA;
                    color:#fff;
                    text-decoration:none;
                    padding:12px 20px;
                    border-radius:8px;
                    display:inline-block;
                    font-weight:700
                "
            >
                Redefinir minha senha
            </a>
        </p>

        <p style="font-size:13px;color:#667085">
            Se você não solicitou essa alteração,
            ignore este e-mail.
        </p>
    </div>
    """

    _enviar_resend(
        destinatario,
        "Redefinição de senha - SPY TEAM",
        corpo_html,
        api_key=api_key,
        remetente=remetente
    )


# ============================================================
# VERIFICAÇÃO / TROCA DE E-MAIL
# ============================================================

def enviar_email_verificacao(
    destinatario: str,
    token: str,
    *,
    troca: bool = False
) -> None:
    """Envia um link de confirmação para cadastro ou troca de e-mail."""

    link = criar_link_verificacao_email(token)
    modo, api_key, remetente = _config_email()

    if modo == "console":
        print(
            "[SpyTeam] Link de verificação de e-mail para",
            destinatario,
            ":",
            link
        )
        return

    destinatario_html = html.escape(destinatario)
    link_html = html.escape(link, quote=True)

    titulo = (
        "Confirme seu novo e-mail"
        if troca
        else "Confirme seu e-mail"
    )

    texto = (
        "Você solicitou a troca do e-mail da sua conta SPY TEAM."
        if troca
        else "Seu e-mail foi informado para uma conta SPY TEAM."
    )

    corpo_html = f"""
    <div style="
        font-family:Arial,sans-serif;
        max-width:560px;
        margin:auto;
        color:#101828
    ">
        <h2 style="color:#3161CA">
            {titulo} - SPY TEAM
        </h2>

        <p>{texto}</p>

        <p>
            Confirme o endereço
            <strong>{destinatario_html}</strong>
            usando o botão abaixo. O link expira em 30 minutos.
        </p>

        <p style="margin:28px 0">
            <a
                href="{link_html}"
                style="
                    background:#3161CA;
                    color:#fff;
                    text-decoration:none;
                    padding:12px 20px;
                    border-radius:8px;
                    display:inline-block;
                    font-weight:700
                "
            >
                Confirmar e-mail
            </a>
        </p>

        <p style="font-size:13px;color:#667085">
            Se você não solicitou esta confirmação,
            ignore este e-mail. Nenhuma alteração será feita.
        </p>
    </div>
    """

    _enviar_resend(
        destinatario,
        f"{titulo} - SPY TEAM",
        corpo_html,
        api_key=api_key,
        remetente=remetente
    )

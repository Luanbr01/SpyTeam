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


def enviar_email_recuperacao(
    destinatario: str,
    token: str
) -> None:
    """
    Envia o link de recuperação usando o SDK oficial do Resend.

    Em desenvolvimento:
    EMAIL_MODE=console imprime o link no terminal,
    sem enviar um e-mail real.
    """

    link = criar_link_recuperacao(token)

    modo = os.getenv(
        "EMAIL_MODE",
        "resend"
    ).strip().lower()

    if modo == "console":
        print(
            "[SpyTeam] Link de recuperação para",
            destinatario,
            ":",
            link
        )
        return

    api_key = os.getenv(
        "RESEND_API_KEY",
        ""
    ).strip()

    remetente = os.getenv(
        "EMAIL_FROM",
        ""
    ).strip()

    if not api_key:
        raise RuntimeError(
            "RESEND_API_KEY não configurado."
        )

    if not remetente:
        raise RuntimeError(
            "EMAIL_FROM não configurado."
        )

    destinatario_html = html.escape(
        destinatario
    )

    link_html = html.escape(
        link,
        quote=True
    )

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

        <p style="
            font-size:13px;
            color:#667085
        ">
            Se você não solicitou essa alteração,
            ignore este e-mail.
        </p>
    </div>
    """

    # SDK oficial do Resend.
    resend.api_key = api_key

    try:
        resposta = resend.Emails.send({
            "from": remetente,
            "to": [destinatario],
            "subject":
                "Redefinição de senha - SPY TEAM",
            "html": corpo_html,
        })

        # O SDK normalmente retorna um objeto/dicionário com o id.
        # Se a API rejeitar a chamada, o SDK lança uma exceção.
        if not resposta:
            raise RuntimeError(
                "O Resend não retornou confirmação do envio."
            )

    except Exception as erro:
        raise RuntimeError(
            "Falha ao enviar e-mail pelo Resend: "
            f"{erro}"
        ) from erro

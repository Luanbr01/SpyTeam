# ============================================================
# PUSH_SERVICE.PY
# Notificações Web Push da PWA do SPY TEAM
# ============================================================

import json
import os
import time

from pywebpush import webpush, WebPushException

from .database import SessionLocal
from . import models


def _env(nome: str) -> str:
    return str(os.getenv(nome) or "").strip()


def chave_publica_vapid() -> str:
    return _env("VAPID_PUBLIC_KEY")


def push_configurado() -> bool:
    return bool(
        chave_publica_vapid()
        and _env("VAPID_PRIVATE_KEY")
    )


def _vapid_subject() -> str:
    return (
        _env("VAPID_SUBJECT")
        or "mailto:noreply@spyteam.com.br"
    )


def _payload(
    titulo: str,
    corpo: str,
    url: str = "/aluno",
    tag: str | None = None
) -> str:
    return json.dumps(
        {
            "title": titulo,
            "body": corpo,
            "url": url,
            "tag": tag or "spyteam",
            "icon": "/static/img/pwa-192.png",
            "badge": "/static/img/pwa-192.png"
        },
        ensure_ascii=False
    )


def enviar_push_para_usuario_id(
    usuario_id: int,
    titulo: str,
    corpo: str,
    url: str = "/aluno",
    tag: str | None = None
) -> int:
    """Envia uma notificação para todos os navegadores ativos do usuário."""

    if not push_configurado():
        return 0

    db = SessionLocal()
    enviados = 0

    try:
        assinaturas = (
            db.query(models.PushSubscription)
            .filter(
                models.PushSubscription.usuario_id == usuario_id,
                models.PushSubscription.ativo.is_(True)
            )
            .all()
        )

        if not assinaturas:
            return 0

        dados = _payload(
            titulo=titulo,
            corpo=corpo,
            url=url,
            tag=tag
        )

        for assinatura in assinaturas:
            try:
                webpush(
                    subscription_info={
                        "endpoint": assinatura.endpoint,
                        "keys": {
                            "p256dh": assinatura.p256dh,
                            "auth": assinatura.auth
                        }
                    },
                    data=dados,
                    vapid_private_key=_env("VAPID_PRIVATE_KEY"),
                    vapid_claims={
                        "sub": _vapid_subject()
                    },
                    ttl=60 * 60 * 24
                )

                enviados += 1

            except WebPushException as erro:
                status_code = getattr(erro, "status_code", None)

                # 404/410 significam normalmente que a assinatura
                # daquele navegador deixou de existir.
                if status_code in (404, 410):
                    assinatura.ativo = False
                    assinatura.atualizado_em = int(time.time())

                print(
                    "[SpyTeam] Falha Web Push "
                    f"usuario={usuario_id} status={status_code}: {erro}"
                )

        db.commit()
        return enviados

    finally:
        db.close()


def enviar_push_para_aluno_id(
    aluno_id: int,
    titulo: str,
    corpo: str,
    url: str = "/aluno",
    tag: str | None = None
) -> int:
    """Resolve a conta vinculada ao aluno e envia o Web Push."""

    if not push_configurado():
        return 0

    db = SessionLocal()

    try:
        usuario = (
            db.query(models.Usuario)
            .filter(
                models.Usuario.aluno_id == aluno_id,
                models.Usuario.tipo == "aluno"
            )
            .first()
        )

        if not usuario:
            return 0

        usuario_id = usuario.id

    finally:
        db.close()

    return enviar_push_para_usuario_id(
        usuario_id=usuario_id,
        titulo=titulo,
        corpo=corpo,
        url=url,
        tag=tag
    )

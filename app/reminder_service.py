# ============================================================
# REMINDER_SERVICE.PY
# Lembretes automáticos de treino para a PWA do SPY TEAM
# ============================================================

import asyncio
import os
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError

from .database import SessionLocal
from . import models
from .push_service import enviar_push_para_usuario_id, push_configurado


DEFAULT_TIMEZONE = "America/Sao_Paulo"
DEFAULT_REMINDER_TIME = "07:00"
DEFAULT_PENDING_TIME = "19:00"

_task_agendador = None


def _intervalo_segundos() -> int:
    try:
        valor = int(os.getenv("PUSH_REMINDER_POLL_SECONDS", "60"))
    except ValueError:
        valor = 60

    # Evita polling acidentalmente agressivo.
    return max(30, min(valor, 900))


def _minutos_do_dia(valor: str, padrao: str) -> int:
    texto = str(valor or padrao).strip()

    try:
        hora_texto, minuto_texto = texto.split(":", 1)
        hora = int(hora_texto)
        minuto = int(minuto_texto)

        if 0 <= hora <= 23 and 0 <= minuto <= 59:
            return (hora * 60) + minuto
    except (TypeError, ValueError):
        pass

    return _minutos_do_dia(padrao, "00:00") if valor != padrao else 0


def _timezone_seguro(nome: str):
    try:
        return ZoneInfo(str(nome or DEFAULT_TIMEZONE).strip())
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def _preferencias_usuario(db, usuario_id: int):
    preferencias = (
        db.query(models.PreferenciaNotificacao)
        .filter(models.PreferenciaNotificacao.usuario_id == usuario_id)
        .first()
    )

    if preferencias is not None:
        return preferencias

    preferencias = models.PreferenciaNotificacao(
        usuario_id=usuario_id,
        novo_treino=True,
        lembrete_treino=True,
        treino_pendente=True,
        horario_lembrete=DEFAULT_REMINDER_TIME,
        horario_pendente=DEFAULT_PENDING_TIME,
        timezone=DEFAULT_TIMEZONE,
        atualizado_em=int(time.time())
    )
    db.add(preferencias)
    db.commit()
    db.refresh(preferencias)
    return preferencias


def _reservar_envio(db, usuario_id: int, treino_id: int, tipo: str, data_ref: str):
    registro = models.NotificacaoTreinoEnviada(
        usuario_id=usuario_id,
        treino_id=treino_id,
        tipo=tipo,
        data_referencia=data_ref,
        criado_em=int(time.time())
    )

    db.add(registro)

    try:
        db.commit()
        db.refresh(registro)
        return registro
    except IntegrityError:
        db.rollback()
        return None


def _desfazer_reserva(db, registro_id: int):
    registro = (
        db.query(models.NotificacaoTreinoEnviada)
        .filter(models.NotificacaoTreinoEnviada.id == registro_id)
        .first()
    )

    if registro:
        db.delete(registro)
        db.commit()


def _icone_modalidade(modalidade: str) -> str:
    chave = str(modalidade or "").strip().lower()

    if "nata" in chave:
        return "🏊"
    if "muscula" in chave:
        return "🏋️"
    return "🏃"


def _processar_usuario(usuario_id: int, agora_utc: datetime):
    db = SessionLocal()

    try:
        usuario = (
            db.query(models.Usuario)
            .filter(
                models.Usuario.id == usuario_id,
                models.Usuario.tipo == "aluno",
                models.Usuario.aluno_id.is_not(None)
            )
            .first()
        )

        if not usuario:
            return 0

        # Sem aparelho ativo não há motivo para reservar lembretes.
        tem_assinatura = (
            db.query(models.PushSubscription)
            .filter(
                models.PushSubscription.usuario_id == usuario.id,
                models.PushSubscription.ativo.is_(True)
            )
            .first()
        )

        if not tem_assinatura:
            return 0

        preferencias = _preferencias_usuario(db, usuario.id)
        fuso = _timezone_seguro(preferencias.timezone)
        agora_local = agora_utc.astimezone(fuso)
        hoje = agora_local.date().isoformat()
        minutos_agora = (agora_local.hour * 60) + agora_local.minute
        minutos_lembrete = _minutos_do_dia(
            preferencias.horario_lembrete,
            DEFAULT_REMINDER_TIME
        )
        minutos_pendente = _minutos_do_dia(
            preferencias.horario_pendente,
            DEFAULT_PENDING_TIME
        )

        treinos = (
            db.query(models.TreinoAgendado)
            .filter(
                models.TreinoAgendado.aluno_id == usuario.aluno_id,
                models.TreinoAgendado.data_planejada == hoje,
                models.TreinoAgendado.concluido.is_(False)
            )
            .order_by(models.TreinoAgendado.id.asc())
            .all()
        )

        enviados_total = 0

        for treino in treinos:
            tipo = None

            # Depois do horário de pendência, o aviso de pendente tem
            # prioridade. Assim, se o servidor reiniciar à noite, ele não
            # envia o lembrete da manhã e o aviso da noite juntos.
            if preferencias.treino_pendente and minutos_agora >= minutos_pendente:
                tipo = "treino_pendente"
            elif preferencias.lembrete_treino and minutos_agora >= minutos_lembrete:
                tipo = "lembrete_treino"

            if not tipo:
                continue

            reserva = _reservar_envio(
                db=db,
                usuario_id=usuario.id,
                treino_id=treino.id,
                tipo=tipo,
                data_ref=hoje
            )

            if reserva is None:
                continue

            icone = _icone_modalidade(treino.modalidade)

            if tipo == "treino_pendente":
                titulo = "Treino pendente ⏰"
                corpo = (
                    f"{icone} {treino.modalidade} • {treino.titulo} ainda está pendente hoje."
                )
            else:
                titulo = "Treino de hoje 💪"
                corpo = (
                    f"{icone} {treino.modalidade} • {treino.titulo}. Toque para ver os detalhes."
                )

            enviados = enviar_push_para_usuario_id(
                usuario_id=usuario.id,
                titulo=titulo,
                corpo=corpo,
                url=f"/aluno?treino={treino.id}",
                tag=f"{tipo}-{treino.id}-{hoje}",
                tipo_preferencia=tipo
            )

            if enviados <= 0:
                # A assinatura pode ter expirado entre a consulta e o envio.
                # Removemos a reserva para permitir nova tentativa futura.
                _desfazer_reserva(db, reserva.id)
            else:
                enviados_total += enviados

        return enviados_total

    finally:
        db.close()


def processar_lembretes_agora(agora_utc: datetime | None = None) -> int:
    """Executa um ciclo. Também é usado pelos testes do projeto."""

    if not push_configurado():
        return 0

    if agora_utc is None:
        agora_utc = datetime.now(timezone.utc)
    elif agora_utc.tzinfo is None:
        agora_utc = agora_utc.replace(tzinfo=timezone.utc)

    db = SessionLocal()

    try:
        usuarios = [
            linha[0]
            for linha in (
                db.query(models.Usuario.id)
                .filter(
                    models.Usuario.tipo == "aluno",
                    models.Usuario.aluno_id.is_not(None)
                )
                .all()
            )
        ]
    finally:
        db.close()

    total = 0

    for usuario_id in usuarios:
        try:
            total += _processar_usuario(usuario_id, agora_utc)
        except Exception as erro:
            print(
                "[SpyTeam] Falha ao processar lembretes "
                f"usuario={usuario_id}: {erro}"
            )

    return total


async def _loop_agendador():
    intervalo = _intervalo_segundos()

    # Pequeno atraso para o processo terminar de subir antes da primeira rodada.
    await asyncio.sleep(5)

    while True:
        try:
            await asyncio.to_thread(processar_lembretes_agora)
        except asyncio.CancelledError:
            raise
        except Exception as erro:
            print(f"[SpyTeam] Erro no agendador de notificações: {erro}")

        await asyncio.sleep(intervalo)


def iniciar_agendador_notificacoes():
    global _task_agendador

    if _task_agendador and not _task_agendador.done():
        return

    _task_agendador = asyncio.create_task(_loop_agendador())
    print(
        "[SpyTeam] Agendador de notificações iniciado "
        f"(intervalo={_intervalo_segundos()}s)."
    )


async def parar_agendador_notificacoes():
    global _task_agendador

    if not _task_agendador:
        return

    _task_agendador.cancel()

    try:
        await _task_agendador
    except asyncio.CancelledError:
        pass

    _task_agendador = None

"""Integração direta: os dados das atividades não são persistidos nem compartilhados."""
import base64
import hashlib
import os
import math
import secrets
import time
from urllib.parse import urlencode, urlparse

import requests
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError

from .auth import COOKIE_NAME
from .database import SessionLocal
from .models import StravaConexao


def config():
    return {
        "client_id": os.getenv("STRAVA_CLIENT_ID", "").strip(),
        "client_secret": os.getenv("STRAVA_CLIENT_SECRET", "").strip(),
        "redirect_uri": os.getenv("STRAVA_REDIRECT_URI", "").strip(),
    }


def enabled():
    c = config()
    uri = urlparse(c["redirect_uri"])
    return bool(all(c.values()) and os.getenv("SPYTEAM_SECRET") and
                uri.scheme == "https" and uri.netloc and
                uri.path == "/api/strava/callback" and not uri.query and not uri.fragment)


def cipher():
    secret = os.getenv("SPYTEAM_SECRET")
    if not secret:
        raise HTTPException(503, "Integração Strava aguardando configuração.")
    key = hashlib.sha256(b"spyteam-strava-v1\x00" + secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(value):
    return cipher().encrypt(value.encode()).decode()


def decrypt(value):
    try:
        return cipher().decrypt(value.encode()).decode()
    except (InvalidToken, AttributeError):
        raise HTTPException(409, "Reconecte sua conta Strava para renovar o acesso.") from None


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class StravaError(Exception):
    def __init__(self, status):
        self.status = status


def api(method, path, *, token=None, data=None, params=None):
    """Sem URLs recebidas do cliente, redirects ou conteúdo remoto nos erros/logs."""
    try:
        response = requests.request(
            method, "https://www.strava.com" + path,
            headers={"Authorization": "Bearer " + token} if token else {},
            data=data, params=params, timeout=(5, 15), allow_redirects=False,
        )
        if not 200 <= response.status_code < 300:
            raise StravaError(response.status_code)
        return response.json()
    except (requests.RequestException, ValueError):
        raise StravaError(502) from None


def http_error(exc):
    if exc.status == 429:
        return HTTPException(429, "Limite do Strava atingido. Tente novamente mais tarde.")
    if exc.status in (400, 401, 403):
        return HTTPException(409, "O Strava não autorizou o acesso. Reconecte sua conta.")
    return HTTPException(502, "Strava indisponível no momento. Tente novamente.")


def save_tokens(row, data):
    try:
        access, refresh, expires = data["access_token"], data["refresh_token"], int(data["expires_at"])
        if not isinstance(access, str) or not isinstance(refresh, str) or not access or not refresh:
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise StravaError(502) from None
    row.access_token = encrypt(access)
    row.refresh_token = encrypt(refresh)
    row.expires_at = expires


def access_token(row, db, force=False):
    # Caller holds the PostgreSQL row lock, serializing refresh-token rotation.
    if force or row.expires_at <= int(time.time()) + 60:
        c = config()
        result = api("POST", "/oauth/token", data={
            "client_id": c["client_id"], "client_secret": c["client_secret"],
            "grant_type": "refresh_token", "refresh_token": decrypt(row.refresh_token),
        })
        save_tokens(row, result)
        db.flush()
    return decrypt(row.access_token)


def locked_connection(db, uid):
    return db.query(StravaConexao).filter_by(usuario_id=uid).with_for_update().first()


def verify_revocation(atleta_id):
    """Webhook não é assinado pelo Strava: confirma a revogação antes de apagar."""
    with SessionLocal() as db:
        row = db.query(StravaConexao).filter_by(atleta_id=str(atleta_id)).with_for_update().first()
        if not row or not row.access_token:
            return
        try:
            api("GET", "/api/v3/athlete", token=access_token(row, db))
            db.commit()
        except StravaError as exc:
            if exc.status not in (400, 401):
                db.rollback()
                return
            try:
                token = access_token(row, db, force=True)
                api("GET", "/api/v3/athlete", token=token)
                db.commit()
            except StravaError as final:
                if final.status in (400, 401):
                    db.delete(row)
                    db.commit()
                else:
                    db.rollback()
        except HTTPException:
            db.rollback()


def activity_summary(activity):
    """Whitelist de dados do próprio atleta; sem tokens, outros atletas ou streams."""
    def number(key):
        value = activity.get(key)
        if value is None or isinstance(value, bool):
            return None
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) and value >= 0 else None

    route = activity.get("map") or {}
    polyline = route.get("summary_polyline") if isinstance(route, dict) else None
    if not isinstance(polyline, str) or len(polyline) > 200000:
        polyline = None
    return {
        "id": str(int(activity["id"])), "name": str(activity.get("name") or "Atividade"),
        "sport_type": activity.get("sport_type") or activity.get("type") or "Workout",
        "start_date": activity.get("start_date"),
        "start_date_local": activity.get("start_date_local"),
        "distance": number("distance"), "moving_time": number("moving_time"),
        "elapsed_time": number("elapsed_time"), "average_speed": number("average_speed"),
        "total_elevation_gain": number("total_elevation_gain"),
        "summary_polyline": polyline,
    }


def build_router(require_aluno, get_db):
    router = APIRouter(prefix="/api/strava", tags=["Strava"])

    @router.get("/status")
    def status(usuario=Depends(require_aluno), db=Depends(get_db)):
        row = db.get(StravaConexao, usuario.id)
        return JSONResponse({"enabled": enabled(), "connected": bool(row and row.atleta_id),
                             "last_sync": row.last_sync if row else 0,
                             "next_sync_in": max(0, 30 - (int(time.time()) - row.last_sync)) if row else 0},
                            headers={"Cache-Control": "no-store"})

    @router.post("/connect")
    def connect(request: Request, usuario=Depends(require_aluno), db=Depends(get_db)):
        if not enabled():
            raise HTTPException(503, "Integração Strava aguardando configuração.")
        row = locked_connection(db, usuario.id)
        if not row:
            row = StravaConexao(usuario_id=usuario.id)
            db.add(row)
        state = secrets.token_urlsafe(32)
        row.state_hash = digest(state)
        row.session_hash = digest(request.cookies.get(COOKIE_NAME, ""))
        row.state_expires = int(time.time()) + 600
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Uma conexão já foi iniciada. Tente novamente.") from None
        c = config()
        query = urlencode({"client_id": c["client_id"], "redirect_uri": c["redirect_uri"],
                           "response_type": "code", "approval_prompt": "force",
                           "scope": "read,activity:read", "state": state})
        return JSONResponse({"url": "https://www.strava.com/oauth/authorize?" + query},
                            headers={"Cache-Control": "no-store"})

    @router.get("/callback")
    def callback(request: Request, usuario=Depends(require_aluno), db=Depends(get_db)):
        def back(result):
            return RedirectResponse("/aluno/strava?strava=" + result, status_code=303,
                                    headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        state = request.query_params.get("state", "")
        # Consumo atômico: evita replay mesmo em múltiplos workers.
        updated = db.query(StravaConexao).filter(
            StravaConexao.usuario_id == usuario.id,
            StravaConexao.state_hash == digest(state),
            StravaConexao.session_hash == digest(request.cookies.get(COOKIE_NAME, "")),
            StravaConexao.state_expires > int(time.time()),
        ).update({"state_hash": None, "session_hash": None, "state_expires": 0}) if state else 0
        db.commit()
        if not updated:
            return back("expired")
        if request.query_params.get("error"):
            return back("cancelled")
        code = request.query_params.get("code")
        scopes = set(request.query_params.get("scope", "").replace(",", " ").split())
        if not code or "activity:read" not in scopes:
            return back("scope")
        if not enabled():
            return back("error")
        try:
            c = config()
            data = api("POST", "/oauth/token", data={
                "client_id": c["client_id"], "client_secret": c["client_secret"],
                "code": code, "grant_type": "authorization_code",
            })
            athlete = str(int(data["athlete"]["id"]))
            row = locked_connection(db, usuario.id)
            if row is None:
                return back("expired")
            # Não transfere uma conta Strava de outro aluno silenciosamente.
            other = db.query(StravaConexao).filter(StravaConexao.atleta_id == athlete,
                                                  StravaConexao.usuario_id != usuario.id).first()
            if other:
                return back("linked")
            save_tokens(row, data)
            row.atleta_id, row.scopes, row.last_sync = athlete, " ".join(sorted(scopes)), 0
            db.commit()
            return back("connected")
        except IntegrityError:
            db.rollback()
            return back("linked")
        except (StravaError, KeyError, ValueError, TypeError):
            db.rollback()
            return back("error")

    @router.post("/sync")
    def sync(usuario=Depends(require_aluno), db=Depends(get_db)):
        if not enabled():
            raise HTTPException(503, "Integração Strava aguardando configuração.")
        row = locked_connection(db, usuario.id)
        if not row or not row.atleta_id:
            raise HTTPException(409, "Conecte sua conta Strava primeiro.")
        now = int(time.time())
        if row.last_sync and now - row.last_sync < 30:
            raise HTTPException(429, "Aguarde alguns segundos entre atualizações.",
                                headers={"Retry-After": str(30 - (now - row.last_sync))})
        try:
            token = access_token(row, db)
            try:
                data = api("GET", "/api/v3/athlete/activities", token=token,
                           params={"page": 1, "per_page": 30})
            except StravaError as exc:
                if exc.status != 401:
                    raise
                token = access_token(row, db, force=True)
                data = api("GET", "/api/v3/athlete/activities", token=token,
                           params={"page": 1, "per_page": 30})
            if not isinstance(data, list):
                raise StravaError(502)
            activities = [activity_summary(a) for a in data]
            row.last_sync = now
            db.commit()
            return JSONResponse({"activities": activities, "synced_at": now},
                                headers={"Cache-Control": "no-store"})
        except StravaError as exc:
            # Persiste eventual rotação mesmo se a consulta subsequente falhar.
            db.commit()
            raise http_error(exc) from None
        except (KeyError, TypeError, ValueError):
            db.commit()
            raise HTTPException(502, "Resposta inesperada do Strava. Tente novamente.") from None

    @router.post("/disconnect")
    def disconnect(usuario=Depends(require_aluno), db=Depends(get_db)):
        row = locked_connection(db, usuario.id)
        if row and row.atleta_id:
            try:
                token = access_token(row, db)
                api("POST", "/oauth/deauthorize", token=token)
            except StravaError as exc:
                if exc.status not in (400, 401):
                    db.commit()
                    raise http_error(exc) from None
            except HTTPException:
                # Chave alterada: permite apagar tokens irrecuperáveis localmente.
                db.delete(row)
                db.commit()
                return {"message": "Conexão local removida. Revogue também em Strava > Configurações > Meus aplicativos."}
        if row:
            db.delete(row)
        db.commit()
        return {"message": "Strava desconectado."}

    @router.get("/webhook")
    def webhook_verify(request: Request):
        expected = os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN", "")
        q = request.query_params
        if (not expected or q.get("hub.mode") != "subscribe" or
                not secrets.compare_digest(q.get("hub.verify_token", ""), expected)):
            raise HTTPException(403, "Verificação inválida.")
        return {"hub.challenge": q.get("hub.challenge", "")}

    @router.post("/webhook")
    async def webhook(request: Request, background: BackgroundTasks):
        # Sem cookie/CSRF: este endpoint recebe chamadas servidor-a-servidor.
        body = await request.body()
        if len(body) > 16384:
            raise HTTPException(413, "Evento muito grande.")
        try:
            import json
            event = json.loads(body)
            expected = os.getenv("STRAVA_WEBHOOK_SUBSCRIPTION_ID", "")
            if not expected or str(event.get("subscription_id", "")) != expected:
                raise HTTPException(403, "Assinatura inválida.")
            owner = int(event["owner_id"])
            if event.get("object_type") == "athlete" and str(event.get("updates", {}).get("authorized")).lower() == "false":
                background.add_task(verify_revocation, owner)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise HTTPException(400, "Evento inválido.") from None
        # Atividades são consultadas ao vivo: não há cópias a atualizar/apagar.
        return {"received": True}

    return router

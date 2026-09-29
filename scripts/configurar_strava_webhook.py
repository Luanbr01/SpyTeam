"""Execute no terminal do serviço Railway: python scripts/configurar_strava_webhook.py"""
import os
from urllib.parse import urlsplit, urlunsplit
import requests


def main():
    client_id = os.getenv("STRAVA_CLIENT_ID", "")
    secret = os.getenv("STRAVA_CLIENT_SECRET", "")
    verify = os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN", "")
    redirect = urlsplit(os.getenv("STRAVA_REDIRECT_URI", ""))
    if not client_id or not secret or not verify or redirect.scheme != "https" or not redirect.netloc:
        raise SystemExit("Configure STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REDIRECT_URI e STRAVA_WEBHOOK_VERIFY_TOKEN no serviço.")
    callback = urlunsplit((redirect.scheme, redirect.netloc, "/api/strava/webhook", "", ""))
    endpoint = "https://www.strava.com/api/v3/push_subscriptions"
    credentials = {"client_id": client_id, "client_secret": secret}
    try:
        response = requests.get(endpoint, params=credentials, timeout=(5, 20), allow_redirects=False)
        if response.status_code != 200:
            raise SystemExit(f"Não foi possível consultar assinaturas (HTTP {response.status_code}). Confira as credenciais.")
        subscriptions = response.json()
        existing = next((item for item in subscriptions if item.get("callback_url") == callback), None)
        if existing:
            subscription_id = existing["id"]
        else:
            if subscriptions:
                raise SystemExit("A aplicação já possui um webhook em outro endereço. Nenhuma assinatura foi alterada. Revise antes de continuar.")
            response = requests.post(endpoint, data={**credentials, "callback_url": callback, "verify_token": verify},
                                     timeout=(5, 20), allow_redirects=False)
            if response.status_code != 201:
                raise SystemExit(f"Não foi possível cadastrar o webhook (HTTP {response.status_code}). Confira o deploy, o domínio e o token de verificação.")
            subscription_id = response.json()["id"]
        print("Webhook cadastrado. Adicione esta variável no serviço Railway e aplique o deploy:")
        print(f"STRAVA_WEBHOOK_SUBSCRIPTION_ID={int(subscription_id)}")
    except (requests.RequestException, ValueError, KeyError, TypeError):
        raise SystemExit("Falha ao consultar o Strava. Tente novamente; nenhuma credencial foi exibida.") from None


if __name__ == "__main__":
    main()

# NÃO coloque senhas reais neste arquivo no GitHub.
SPYTEAM_SECRET=gere-uma-chave-longa-e-aleatoria
PROFESSOR_USUARIO=seu_usuario_de_professor
PROFESSOR_SENHA=uma_senha_forte
PROFESSOR_NOME=Nome do Professor
# Opcional. Se definido aqui, é considerado administrativamente verificado.
# PROFESSOR_EMAIL=professor@seudominio.com.br
COOKIE_SECURE=true

# Opcional: o SpyTeam detecta automaticamente o Volume do Railway.
# DATABASE_PATH=/data/assessoria.db

# Recuperação de senha por e-mail (Resend)
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxx
EMAIL_FROM=SPY TEAM <contato@seudominio.com.br>
APP_URL=https://seu-dominio.com.br
EMAIL_MODE=resend

# Em desenvolvimento local, você pode testar sem enviar e-mail real:
# EMAIL_MODE=console

# Rate limit de login (opcional; estes são os valores padrão)
# LOGIN_RATE_WINDOW_SECONDS=900
# LOGIN_RATE_MAX_IP=30
# LOGIN_RATE_MAX_USER_IP=5
# LOGIN_RATE_MAX_USER=20

# Rate limit global da recuperação de senha
# RECOVERY_RATE_WINDOW_SECONDS=900
# RECOVERY_RATE_MAX_IP=10
# RECOVERY_RATE_MAX_IDENTIFIER=3
# RECOVERY_RATE_MAX_GLOBAL=100

# PWA / Web Push
# Gere com: python scripts/gerar_vapid.py
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:noreply@spyteam.com.br

# PWA / lembretes automáticos (opcional)
# Intervalo entre verificações do agendador; mínimo efetivo: 30 segundos.
# PUSH_REMINDER_POLL_SECONDS=60

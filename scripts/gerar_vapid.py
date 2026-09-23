# Gera um par VAPID para Web Push.
# Execute UMA VEZ localmente e copie os valores para Railway > Variables.

import base64

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization


def b64url(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


chave = ec.generate_private_key(ec.SECP256R1())

privada_der = chave.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

publica_raw = chave.public_key().public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint
)

print("VAPID_PUBLIC_KEY=" + b64url(publica_raw))
print("VAPID_PRIVATE_KEY=" + b64url(privada_der))
print("VAPID_SUBJECT=mailto:noreply@spyteam.com.br")

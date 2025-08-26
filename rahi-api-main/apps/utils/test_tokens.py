import uuid
from datetime import datetime, timedelta

import jwt


def generate_test_token() -> str:
    with open("keys/test/private_key.pem", "rb") as f:
        private_key = f.read()

    payload = {"sub": str(uuid.uuid4()), "exp": datetime.now() + timedelta(minutes=10)}

    jwt_token = jwt.encode(payload, private_key, algorithm="RS256")
    return jwt_token


def decode_test_token(token: str) -> str | None:
    with open("keys/test/public_key.pem", "rb") as f:
        public_key = f.read()

    try:
        decoded_payload = jwt.decode(token, public_key, algorithms=["RS256"])
        return decoded_payload["sub"]
    except jwt.InvalidTokenError:
        raise jwt.InvalidTokenError("invalid token")

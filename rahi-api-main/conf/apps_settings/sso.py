from environs import Env

env = Env()
env.read_env()

CLIENT_ID = env.str("CLIENT_ID")
CLIENT_SECRET = env.str("CLIENT_SECRET")
CODE_VERIFIER = env.str("CODE_VERIFIER")
CODE_CHALLENGE = env.str("CODE_CHALLENGE")
REDIRECT_URI = env.str("REDIRECT_URI")
SSO_BASE_URL = env.str("SSO_BASE_URL")

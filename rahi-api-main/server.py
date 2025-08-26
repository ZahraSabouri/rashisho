import os

from waitress import serve

from conf.wsgi import application

if __name__ == "__main__":
    if os.getenv("ASGI", "0") == "0":
        serve(application, host="0.0.0.0", port=8000, threads=int(os.getenv("WSGI_THREADS", 2048)))
    else:
        workers = os.getenv("WEB_CONCURRENCY", 32)
        os.system(f"poetry run python -m uvicorn --host 0.0.0.0 --port 8000 --workers {workers} conf.asgi:application")

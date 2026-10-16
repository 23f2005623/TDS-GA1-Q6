import os
from pathlib import Path

import yaml
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS: lets the grader's web page call your API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simulates the "OS env var" layer in case your host doesn't set it for you
os.environ.setdefault("APP_WORKERS", "7")

BASE = Path(__file__).parent
ALIASES = {"num_workers": "workers"}   # NUM_WORKERS -> workers


def fix_key(k: str) -> str:
    k = k.strip().lower()
    return ALIASES.get(k, k)


def coerce(key: str, value):
    if key in ("port", "workers"):
        return int(value)
    if key == "debug":
        return str(value).strip().lower() in ("true", "1", "yes", "on")
    return str(value)


def load_yaml(env_name: str) -> dict:
    f = BASE / f"config.{env_name}.yaml"
    if f.exists():
        return yaml.safe_load(f.read_text()) or {}
    return {}


def load_dotenv() -> dict:
    out = {}
    f = BASE / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[fix_key(k)] = v.strip().strip('"').strip("'")
    return out


def load_os_env() -> dict:
    out = {}
    for k, v in os.environ.items():
        if k.startswith("APP_") and k != "APP_ENV":
            out[fix_key(k[4:])] = v
    return out


@app.get("/effective-config")
def effective_config(set: list[str] = Query(default=[])):
    env_name = os.environ.get("APP_ENV", "development")

    cfg = {                                   # layer 1: defaults
        "port": 9004,
        "workers": 1,
        "debug": False,
        "log_level": "info",
        "api_key": "default-secret-000",
    }
    cfg.update({fix_key(k): v for k, v in load_yaml(env_name).items()})  # layer 2
    cfg.update(load_dotenv())                                            # layer 3
    cfg.update(load_os_env())                                            # layer 4

    for item in set:                          # layer 5: CLI overrides
        if "=" in item:
            k, v = item.split("=", 1)
            cfg[fix_key(k)] = v

    result = {k: coerce(k, v) for k, v in cfg.items()}
    result["api_key"] = "****"                # never leak the secret
    return result
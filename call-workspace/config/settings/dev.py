from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Use localhost for local dev without Docker
DATABASES["default"]["HOST"] = env("POSTGRES_HOST", "localhost")

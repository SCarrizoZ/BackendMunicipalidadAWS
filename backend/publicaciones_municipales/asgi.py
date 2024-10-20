"""
ASGI config for publicaciones_municipales project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

from dotenv import load_dotenv, find_dotenv

# Cargar variables desde el archivo .env
load_dotenv(find_dotenv())

os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.getenv("DJANGO_SETTINGS_MODULE"))

application = get_asgi_application()

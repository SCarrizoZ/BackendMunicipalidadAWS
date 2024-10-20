"""
WSGI config for publicaciones_municipales project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

from dotenv import load_dotenv, find_dotenv

# Cargar variables desde el archivo .env
load_dotenv(find_dotenv())

os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.getenv("DJANGO_SETTINGS_MODULE"))

application = get_wsgi_application()
# add this vercel variable
app = application

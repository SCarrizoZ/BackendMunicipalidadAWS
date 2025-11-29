#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from dotenv import load_dotenv, find_dotenv

# Cargar variables desde el archivo .env
load_dotenv(find_dotenv())


GTK_FOLDER = r"D:\Programas\GTK3\ucrt64\bin"

if os.name == "nt" and os.path.exists(GTK_FOLDER):
    try:
        os.add_dll_directory(GTK_FOLDER)
    except Exception as e:
        print(f"Error al agregar DLLs de GTK: {e}")
    # Por compatibilidad con versiones anteriores o sistemas mixtos, también agregamos al PATH
    os.environ["PATH"] = GTK_FOLDER + ";" + os.environ["PATH"]

def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.getenv("DJANGO_SETTINGS_MODULE"))
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from dotenv import load_dotenv


if __name__ == "__main__":
    # Automatically load .env.development if it exists
    if os.path.exists(".env.development"):
        load_dotenv(".env.development")
    else:
        load_dotenv(".env")  # fallback to production env

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tyrent_backend.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)

def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tyrent_backend.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.join(ROOT, "backend")

# Set sys.path BEFORE any Django imports so imports resolve correctly
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Configure Django settings module for pytest-django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.test_settings")

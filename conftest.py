import sys
import os

ROOT = os.path.dirname(__file__)
# Set sys.path BEFORE any Django imports so imports resolve correctly
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)

# Configure Django settings module for pytest-django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.test_settings")

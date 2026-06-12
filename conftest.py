import sys
import os

ROOT = os.path.dirname(__file__)
# Ensure backend package and repo root are on sys.path so apps import correctly
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)

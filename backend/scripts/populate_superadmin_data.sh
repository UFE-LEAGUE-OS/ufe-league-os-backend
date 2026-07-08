#!/bin/bash
# Script to populate superadmin test data

cd "$(dirname "$0")/.."
python manage.py --settings=config.test_settings populate_superadmin_data "$@"
#!/bin/bash
# Script to populate governance sample data

echo "Running migrations..."
python backend/manage.py migrate --settings=config.test_settings

echo ""
echo "Populating governance data..."
python backend/manage.py populate_governance_data --settings=config.test_settings

echo ""
echo "Done!"
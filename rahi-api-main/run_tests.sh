#!/bin/bash
set -e  # Configure shell so that if one command fails, it exits
poetry run coverage erase
poetry run coverage run manage.py test apps/*/tests/ 
poetry run coverage report
#!/bin/bash
alias python=python3
# install pre commit
poetry run pre-commit install

# generate RSA keys for development/testing if they don't exist
if [ ! -f "keys/test/private_key.pem" ] || [ ! -f "keys/test/public_key.pem" ]; then
    echo "Generating RSA keys for development..."
    poetry run python generate_keys.py
else
    echo "RSA keys already exist, skipping generation"
fi

# create data base
poetry run python manage.py migrate

# initial settings
poetry run python manage.py shell -c "import docker_init"

# loaddate
poetry run python manage.py loaddata loaddata/province.json
poetry run python manage.py loaddata loaddata/city.json
poetry run python manage.py create_field_studies
poetry run python manage.py create_universities
poetry env info --path

# runs the server
if [ "$WSGI" == "1" ]; then
    uwsgi --chdir=/home/django --buffer-size=62914560 --module conf.wsgi:application --master --processes $WSGI_PROCCESSES --vacuum --max-requests=$WSGI_MAX_REQUESTS --uid $WSGI_UID --gid $WSGI_GID --env DJANGO_SETTINGS_MODULE=conf.settings --socket 0.0.0.0:8000 --protocol http
else
    python server.py
fi
#!/usr/bin/env bash

rm -Rf .env || true

cp requirements.freezed.pip requirements.freezed.$(date +"%Y%m%d%H%M").pip || true

virtualenv .env
source .env/bin/activate

pip install -r requirements.pip
pip freeze --disable-pip-version-check -q -r requirements.pip > requirements.freezed.pip

deactivate
rm -Rf .env

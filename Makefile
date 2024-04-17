.DEFAULT_GOAL := help

NODE_BIN := ./node_modules/.bin

define BROWSER_PYSCRIPT
import os, webbrowser, sys
try:
	from urllib import pathname2url
except:
	from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef
export BROWSER_PYSCRIPT
BROWSER := python -c "$$BROWSER_PYSCRIPT"

help: ## display this help message
	@echo "Please use \`make <target>' where <target> is one of"
	@perl -nle'print $& if m{^[\.a-zA-Z_-]+:.*?## .*$$}' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m  %-25s\033[0m %s\n", $$1, $$2}'

clean: ## remove generated byte code, coverage reports, and build artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -rf {} +
	find . -name '*~' -exec rm -f {} +
	coverage erase
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info

clean.static: ## remove all ignored generated static files
	rm -rf enterprise/assets/
	rm -rf enterprise/static/enterprise/bundles/*.js

static: ## rather all static assets for production
	$(NODE_BIN)/webpack --config webpack.config.js --display-error-details --progress --optimize-minimize
	python manage.py collectstatic --noinput
	# TODO: Add the compression app for manage.py settings.
	#python manage.py compress -v3 --force

static.dev: ## gather all static assets for a development environment
	$(NODE_BIN)/webpack --config webpack.config.js --display-error-details --progress

static.watch: ## watch for static asset changes for a development environment
	$(NODE_BIN)/webpack --config webpack.config.js --display-error-details --progress --watch

compile_translations: ## compile translation files, outputting .po files for each supported language
	./manage.py compilemessages

dummy_translations: ## generate dummy translation (.po) files
	cd enterprise && i18n_tool dummy

extract_translations: ## extract strings to be translated, outputting .mo files
	rm -rf docs/_build
	i18n_tool extract --no-segment

fake_translations: extract_translations dummy_translations compile_translations ## generate and compile dummy translation files

pull_translations: ## pull translations from Transifex
	tx pull -a

push_translations: ## push source translation files (.po) from Transifex
	tx push -s

coverage: clean ## generate and view HTML coverage report
	py.test --cov-report html
	$(BROWSER) htmlcov/index.html

docs: ## generate Sphinx HTML documentation, including API docs
	tox -e docs
	$(BROWSER) docs/_build/html/index.html

# Define PIP_COMPILE_OPTS=-v to get more information during make upgrade.
PIP_COMPILE = pip-compile --upgrade --rebuild $(PIP_COMPILE_OPTS)
LOCAL_EDX_PINS = requirements/edx-platform-constraints.txt
PLATFORM_BASE_REQS = https://raw.githubusercontent.com/openedx/edx-platform/master/requirements/edx/base.txt
COMMON_CONSTRAINTS_TXT=requirements/common_constraints.txt
.PHONY: $(COMMON_CONSTRAINTS_TXT)
$(COMMON_CONSTRAINTS_TXT):
	wget -O "$(@)" https://raw.githubusercontent.com/edx/edx-lint/master/edx_lint/files/common_constraints.txt || touch "$(@)"
	echo "$(COMMON_CONSTRAINTS_TEMP_COMMENT)" | cat - $(@) > temp && mv temp $(@)

check_pins: $(COMMON_CONSTRAINTS_TXT) ## check that our local copy of edx-platform pins is accurate
	echo "### DON'T edit this file, it's copied from edx-platform. See make upgrade" > $(LOCAL_EDX_PINS)
	curl -fsSL $(PLATFORM_BASE_REQS) | grep -v '^-e' | grep -v 'via edx-enterprise$$' >> $(LOCAL_EDX_PINS)
	# These requirement pins are removed because this is causing a deadlock in upgrading celery in both
	# edx-platform and edx-enterprise. Will be resolved after the successful upgrade of celery in platform
	sed -i.tmp '/^amqp==/d' $(LOCAL_EDX_PINS)
	sed -i.tmp '/^anyjson==/d' $(LOCAL_EDX_PINS)
	sed -i.tmp '/^billiard==/d' $(LOCAL_EDX_PINS)
	sed -i.tmp '/^celery==/d' $(LOCAL_EDX_PINS)
	sed -i.tmp '/^kombu==/d' $(LOCAL_EDX_PINS)
	sed -i.tmp '/^click-didyoumean==/d' $(LOCAL_EDX_PINS)
	sed -i.tmp '/^click-repl==/d' $(LOCAL_EDX_PINS)
	sed -i.tmp '/^click==/d' $(LOCAL_EDX_PINS)
	sed -i.tmp '/^prompt-toolkit==/d' $(LOCAL_EDX_PINS)
	sed -i.tmp '/^vine==/d' $(LOCAL_EDX_PINS)
	sed -i.tmp '/^django-simple-history==/d' $(LOCAL_EDX_PINS)


	rm requirements/*.txt.tmp
	python requirements/check_pins.py requirements/test-master.txt $(LOCAL_EDX_PINS)

upgrade: export CUSTOM_COMPILE_COMMAND=make upgrade
upgrade: requirements check_pins ## update the requirements/*.txt files with the latest packages satisfying requirements/*.in
	sed '/^django-simple-history==/d' requirements/common_constraints.txt > requirements/common_constraints.tmp
	mv requirements/common_constraints.tmp requirements/common_constraints.txt
	$(PIP_COMPILE) --no-emit-trusted-host --no-emit-index-url -o requirements/test-master.txt requirements/test-master.in
	$(PIP_COMPILE) --no-emit-trusted-host --no-emit-index-url -o requirements/doc.txt requirements/doc.in
	$(PIP_COMPILE) --no-emit-trusted-host --no-emit-index-url -o requirements/test.txt requirements/test.in
	$(PIP_COMPILE) --no-emit-trusted-host --no-emit-index-url -o requirements/dev.txt requirements/dev.in
	$(PIP_COMPILE) --no-emit-trusted-host --no-emit-index-url -o requirements/ci.txt requirements/ci.in
	$(PIP_COMPILE) --no-emit-trusted-host --no-emit-index-url -o requirements/js_test.txt requirements/js_test.in
	# This section removes django from test.txt to
	# let tox control the Django version for tests
	grep -e "^django==" requirements/test.txt > requirements/django.txt
	grep -e "^amqp==\|^anyjson==\|^billiard==\|^celery==\|^kombu==\|^click-didyoumean==\|^click-repl==\|^click==\|^prompt-toolkit==\|^vine==" requirements/dev.txt > requirements/celery53.txt
	sed -i.tmp '/^[d|D]jango==/d' requirements/test.txt
	sed -i.tmp '/^amqp==/d' requirements/test.txt
	sed -i.tmp '/^anyjson==/d' requirements/test.txt
	sed -i.tmp '/^billiard==/d' requirements/test.txt
	sed -i.tmp '/^celery==/d' requirements/test.txt
	sed -i.tmp '/^kombu==/d' requirements/test.txt
	sed -i.tmp '/^click-didyoumean==/d' requirements/test.txt
	sed -i.tmp '/^click-repl==/d' requirements/test.txt
	sed -i.tmp '/^click==/d' requirements/test.txt
	sed -i.tmp '/^click==/d' requirements/test.txt
	sed -i.tmp '/^prompt-toolkit==/d' requirements/test.txt
	sed -i.tmp '/^vine==/d' requirements/test.txt
	rm requirements/test.txt.tmp

requirements.js: ## install JS requirements for local development
	npm ci

requirements: requirements.js ## install development environment requirements
	pip install -qr requirements/dev.txt --exists-action w
	pip-sync requirements/test-master.txt requirements/dev.txt requirements/private.* requirements/test.txt

jshint: ## run Javascript linting
	@[ -x ./node_modules/jshint/bin/jshint ] || npm install jshint --no-save
	./node_modules/jshint/bin/jshint enterprise
	./node_modules/jshint/bin/jshint spec

test: clean ## run tests in the current virtualenv
	pip install -qr requirements/test.txt --exists-action w
	py.test

diff_cover: test
	diff-cover coverage.xml

test-all: clean jshint static ## run tests on every supported Python/Django combination
	tox
	tox -e quality
	tox -e jasmine

validate: test ## run tests and quality checks
	tox -e quality

quality: ## run python quality checks
	tox -e quality

pylint: ## run pylint outside of tox
	pylint -j 0 enterprise enterprise_learner_portal consent integrated_channels tests test_utils requirements/check_pins.py --django-settings-module=enterprise.settings.test

pycodestyle: ## run pycodestyle outside of tox
	pycodestyle enterprise enterprise_learner_portal consent integrated_channels tests test_utils

pii_check: pii_clean
	tox -e pii-annotations

pii_clean:
	rm -rf pii_report
	mkdir -p pii_report

isort: ## call isort on packages/files that are checked in quality tests
	isort --skip migrations --recursive tests test_utils enterprise enterprise_learner_portal consent integrated_channels manage.py setup.py

## Docker in this repo is only supported for running tests locally
## as an alternative to virtualenv natively - johnnagro 2022-02-11
test-shell: ## Run a shell, as root, on the specified service container
	docker-compose run -u 0 test-shell env TERM=$(TERM) /bin/bash

dev.up.keycloak:
	docker-compose up --detach keycloak

dev.stop.keycloak:
	docker-compose stop keycloak

.PHONY: clean clean.static compile_translations coverage docs dummy_translations extract_translations \
	fake_translations help pull_translations push_translations requirements test test-all upgrade validate isort \
	static static.dev static.watch

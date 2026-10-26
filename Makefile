.DEFAULT_GOAL := help
.PHONY: help test check example lint release vendor

PYTHON ?= python3
CLI = PYTHONPATH=src $(PYTHON) -c 'from champollion.cli import main; raise SystemExit(main())'
EXAMPLE = examples/latin-to-spanish
PROFILE = $(CURDIR)/profiles/latin-to-spanish.json

# Mechanical checks do not translate or certify sense; review is recorded separately (VER-1).
help:
	@$(PYTHON) -c 'print("help     List every target (default)\ntest     Run stdlib unittest discovery\ncheck    Mechanically check the bundled Latin-to-Spanish example\nexample  Report the bundled example, including recorded judgement\nlint     Compile all source and test modules\nrelease  Build reproducible wheel/source archives and SHA256SUMS; do not publish\nvendor   Write a local v1.2.0 snapshot to vendor/champollion")'

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -t .

check:
	$(CLI) check --root "$(EXAMPLE)" --profile "$(PROFILE)"

example:
	$(CLI) report --root "$(EXAMPLE)" --profile "$(PROFILE)"

lint:
	$(PYTHON) -m compileall -q src tests scripts

# Build dependencies must already be installed; the release builder never fetches.
release:
	$(PYTHON) scripts/build-release.py

vendor:
	$(CLI) vendor --into vendor --tag v1.2.0

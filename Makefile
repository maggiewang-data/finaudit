.PHONY: install fetch ask eval test lint

install:
	pip install -r requirements-dev.txt

fetch:            ## download the latest 10-Ks and XBRL ground truth from SEC EDGAR
	cd src && python -m finaudit.sec AAPL UEIC

ask:              ## make ask Q="How much did Apple spend on R&D?"
	cd src && python -m finaudit.pipeline AAPL "$(Q)"

eval:             ## full evaluation -> results/eval.md (about 100 API calls, under $1)
	cd src && python -m finaudit.evaluate

test:
	pytest -q

lint:
	ruff check src tests

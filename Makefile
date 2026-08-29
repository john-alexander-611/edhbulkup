.PHONY: start restart stop test

start:
	powershell -ExecutionPolicy Bypass -File .\run_app.ps1 -Action start

restart:
	powershell -ExecutionPolicy Bypass -File .\run_app.ps1 -Action restart

stop:
	powershell -ExecutionPolicy Bypass -File .\run_app.ps1 -Action stop

test:
	python -m pytest -q

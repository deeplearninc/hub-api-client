clean:
	rm -rf **/*.pyc
	pip uninstall -q -y -r requirements.txt || true

install: clean
	pip install -r requirements.txt

test:
	nose2

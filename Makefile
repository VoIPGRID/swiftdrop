.PHONY: all run

all:
	docker build --pull -t tmp .
	docker build -t harbor.osso.io/spindle/swiftdrop:$(shell git describe) .

run: all
	if test -x examples/run-docker-local.sh; then \
		examples/run-docker-local.sh; \
	else \
		examples/run-docker.sh; \
	fi

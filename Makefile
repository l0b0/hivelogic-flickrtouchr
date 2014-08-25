.PHONY: all
all: test

.PHONY: test
test:
	make virtualenv && \
		. virtualenv/bin/activate && \
		pip install --requirement python-test-requirements.txt && \
		make METHOD=git python-pep8

.PHONY: clean
clean: clean-python

include make-includes/python.mk
include make-includes/variables.mk

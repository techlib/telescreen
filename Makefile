#!/usr/bin/make -f

package = $(shell grep ^Name: *.spec | awk '{print $$2}')
version = $(shell grep ^Version: *.spec | awk '{print $$2}')

pys     = $(shell find telescreen -name '*.py')

all:

dist:
	git clone .git ${package}-${version}
	rm -rf ${package}-${version}/.git
	tar -cvpzf ${package}-${version}.tar.gz ${package}-${version}
	rm -rf ${package}-${version}

pep:
	@python3-pep8 --show-source --ignore=E221,E712 ${pys}


# EOF

LIBS = ./examples/smeagle

all: compile

compile: $(LIBS)/*
	for dir in $^ ; do \
		echo "Building" $${dir} ; \
		$(MAKE) -C $${dir}; \
	done


# Run slicingpie with Docker. Host needs Docker and make.

IMAGE ?= slicingpie
DOCKER ?= docker
ROOT := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))

BOLD := $(shell printf '\033[1m')
CYAN := $(shell printf '\033[36m')
DIM := $(shell printf '\033[2m')
RED := $(shell printf '\033[31m')
RESET := $(shell printf '\033[0m')

ifdef NO_COLOR
BOLD :=
CYAN :=
DIM :=
RED :=
RESET :=
endif

DOCKER_USER := $(shell id -u):$(shell id -g)

# Spinner while a background PID runs. ASCII frames only: | / - backslash
define spin_while
	i=0; \
	while kill -0 $(1) 2>/dev/null; do \
		case $$((i % 4)) in \
			0) frame='|';; \
			1) frame='/';; \
			2) frame='-';; \
			3) frame='\\';; \
		esac; \
		printf '\r%b %s' "$(CYAN)$$frame$(RESET)" "$(2)"; \
		i=$$((i + 1)); \
		sleep 0.1; \
	done; \
	printf '\r\033[K'
endef

# Detect the terminal inside the recipe. A $(shell) check runs in a pipe, so
# it never sees the user's TTY. Empty FORCE_COLOR also makes Rich disable color.
define docker_run
	tty_flag=""; \
	if [ -t 1 ]; then \
		tty_flag="-t"; \
		printf '%b %s' "$(CYAN)|$(RESET)" "Starting slicingpie..."; \
	fi; \
	env_flags="-e HOME=/tmp"; \
	if [ -n "$${TERM-}" ] && [ "$$TERM" != "dumb" ]; then \
		env_flags="$$env_flags -e TERM"; \
	elif [ -n "$$tty_flag" ]; then \
		env_flags="$$env_flags -e TERM=xterm-256color"; \
	fi; \
	if [ -n "$${COLORTERM-}" ]; then env_flags="$$env_flags -e COLORTERM"; fi; \
	if [ -n "$${NO_COLOR-}" ]; then env_flags="$$env_flags -e NO_COLOR"; fi; \
	if [ -n "$${FORCE_COLOR-}" ]; then env_flags="$$env_flags -e FORCE_COLOR"; fi; \
	if [ -n "$${GITHUB_TOKEN-}" ]; then env_flags="$$env_flags -e GITHUB_TOKEN"; fi; \
	if [ -n "$$tty_flag" ]; then printf '\r\033[K'; fi; \
	$(DOCKER) run --rm $$tty_flag \
		--user $(DOCKER_USER) \
		$$env_flags \
		-v "$(ROOT):/work" \
		-w /work \
		$(IMAGE) $(1)
endef

.DEFAULT_GOAL := run
.PHONY: help build run sync-rates test sast verify \
	detail details expenses review verbose json show-skipped show-no-estimate show-unassigned \
	--detail --details --verbose --json --show-skipped --show-no-estimate --show-unassigned

# Extra goals become CLI flags: `make run detail expenses` / `detail review`
# GNU Make treats bare `--details` as its own option, so use a word goal
# (`details`) or stop option parsing: `make run -- --detail review`.
RUN_FLAGS := $(ARGS)
DETAIL_SCOPES := $(filter expenses review,$(MAKECMDGOALS))
ifneq (,$(filter detail details --detail --details,$(MAKECMDGOALS)))
ifneq (,$(DETAIL_SCOPES))
RUN_FLAGS += --detail $(DETAIL_SCOPES)
else
RUN_FLAGS += --detail
endif
endif
ifneq (,$(filter verbose --verbose,$(MAKECMDGOALS)))
RUN_FLAGS += --verbose
endif
ifneq (,$(filter json --json,$(MAKECMDGOALS)))
RUN_FLAGS += --json
endif
ifneq (,$(filter show-skipped --show-skipped,$(MAKECMDGOALS)))
RUN_FLAGS += --show-skipped
endif
ifneq (,$(filter show-no-estimate --show-no-estimate,$(MAKECMDGOALS)))
RUN_FLAGS += --show-no-estimate
endif
ifneq (,$(filter show-unassigned --show-unassigned,$(MAKECMDGOALS)))
RUN_FLAGS += --show-unassigned
endif

detail details expenses review verbose json show-skipped show-no-estimate show-unassigned \
--detail --details --verbose --json --show-skipped --show-no-estimate --show-unassigned:
	@:

help:
	@printf '%b\n' "$(BOLD)$(CYAN)slicingpie$(RESET)  $(DIM)docker$(RESET)"
	@printf '%s\n' "  make run                         pie (local.toml if present, else demo)"
	@printf '%s\n' "  make run detail                  all detail tables (expenses + review)"
	@printf '%s\n' "  make run detail expenses         expense detail by date"
	@printf '%s\n' "  make run detail review           review hours by ticket"
	@printf '%s\n' "  make run details                 same as detail (all)"
	@printf '%s\n' "  make run verbose                 list tickets per person"
	@printf '%s\n' "  make run json                    JSON output"
	@printf '%s\n' "  make run show-skipped            list omitted Done tickets"
	@printf '%s\n' "  make run detail expenses review  both detail tables"
	@printf '%s\n' "  make run -- --detail review      same flags after -- (Make-safe)"
	@printf '%s\n' "  make sync-rates                  repo users into slicingpie.local.toml"
	@printf '%s\n' "  make test                        pytest inside Docker"
	@printf '%s\n' "  make sast                        coverage, complexity, LOC, security"
	@printf '%s\n' "  make build                       build the image"

build:
	@if [ -t 1 ]; then \
		( BUILDKIT_PROGRESS=quiet $(DOCKER) build --quiet -t $(IMAGE) "$(ROOT)" >/dev/null ) & \
		pid=$$!; \
		$(call spin_while,$$pid,Preparing image...); \
		if ! wait $$pid; then \
			$(DOCKER) build -t $(IMAGE) "$(ROOT)"; \
		fi; \
	else \
		BUILDKIT_PROGRESS=quiet $(DOCKER) build --quiet -t $(IMAGE) "$(ROOT)" >/dev/null \
			|| $(DOCKER) build -t $(IMAGE) "$(ROOT)"; \
	fi

run: build
	@$(call docker_run,$(RUN_FLAGS))

sync-rates: build
	@if [ ! -f "$(ROOT)/slicingpie.local.toml" ]; then \
		printf '%b\n' "$(BOLD)$(RED)Missing slicingpie.local.toml$(RESET)"; \
		printf '%b\n' "Copy slicingpie.toml.example and fill in the Project."; \
		exit 1; \
	fi
	@$(call docker_run,--sync-rates $(RUN_FLAGS))

test: build
	@$(DOCKER) run --rm --entrypoint pytest $(IMAGE)

sast: build
	@tty_flag=""; \
	if [ -t 1 ]; then \
		tty_flag="-t"; \
		printf '%b %s\n' "$(CYAN)|$(RESET)" "Running SAST..."; \
	fi; \
	env_flags="-e HOME=/tmp -e PYTHONPATH=/work/src"; \
	if [ -n "$${TERM-}" ] && [ "$$TERM" != "dumb" ]; then \
		env_flags="$$env_flags -e TERM"; \
	elif [ -n "$$tty_flag" ]; then \
		env_flags="$$env_flags -e TERM=xterm-256color"; \
	fi; \
	if [ -n "$${COLORTERM-}" ]; then env_flags="$$env_flags -e COLORTERM"; fi; \
	if [ -n "$${NO_COLOR-}" ]; then env_flags="$$env_flags -e NO_COLOR"; fi; \
	if [ -n "$${FORCE_COLOR-}" ]; then env_flags="$$env_flags -e FORCE_COLOR"; fi; \
	$(DOCKER) run --rm $$tty_flag \
		$$env_flags \
		-v "$(ROOT):/work" \
		-w /work \
		--entrypoint python \
		$(IMAGE) -m slicingpie.sast

verify: test

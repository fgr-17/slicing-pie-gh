FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --all-groups

COPY src ./src
COPY tests ./tests
COPY slicingpie.toml slicingpie.toml.example sast-thresholds.txt mike-moyer-model.toml ./
RUN uv sync --frozen --all-groups

ENTRYPOINT ["slicingpie"]

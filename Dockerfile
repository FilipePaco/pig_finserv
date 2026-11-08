# Runtime image for the Pig FinServ CLI. Local data and secrets are mounted at run time.
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --group ml --group reporting --no-install-project

COPY . ./
RUN uv sync --locked --no-dev --group ml --group reporting

ENTRYPOINT ["uv", "run", "--no-sync", "pig-finserv"]
CMD ["--help"]

# Use an official, lightweight Python runtime
FROM python:3.11-slim

# Install system dependencies needed for git-based pip installations
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv directly from the official binaries
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory inside the container
WORKDIR /app

# Install the dependencies using uv for maximum speed and caching efficiency
# We pass the git URL explicitly as requested
RUN uv pip install --system \
    fastmcp \
    "openfast-toolbox @ git+https://github.com/OpenFAST/openfast_toolbox"

# Create the dedicated folder where models will be read, parsed, and written
RUN mkdir -p /app/models

# Copy the server source code into the container
COPY openfast_mcp.py /app/openfast_mcp.py

# Copy initial local models/templates into the container layout
COPY models /app/models

# Expose the models directory as a volume to allow persistent writes 
# and easy mounting from the host system at runtime
VOLUME ["/app/models"]

# Environment variable to explicitly ensure Python logs output instantly
ENV PYTHONUNBUFFERED=1

# Run the MCP server over standard input/output (stdio)
# Updated to point to openfast_mcp.py instead of server.py
ENTRYPOINT ["python", "/app/src/openfast_mooring_manager/openfast_mcp.py"]
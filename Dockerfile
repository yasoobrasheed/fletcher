# Dockerfile for isolated Claude Code agent environment
FROM ubuntu:22.04

# Avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    python3 \
    python3-pip \
    tmux \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x from NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && \
    chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null && \
    apt-get update && \
    apt-get install -y gh && \
    rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Create a non-root user for running agents
RUN useradd -m -s /bin/bash agent && \
    mkdir -p /workspace && \
    chown -R agent:agent /workspace

# Set working directory
WORKDIR /workspace

# Switch to non-root user
USER agent

# Set environment variables
ENV HOME=/home/agent
ENV USER=agent

# Default command (will be overridden when running)
CMD ["/bin/bash"]

FROM python:3.11-slim

# Install SSH server
RUN apt-get update && apt-get install -y openssh-server && rm -rf /var/lib/apt/lists/*

# Create user with password
RUN useradd -m -s /bin/bash user && echo "user:user" | chpasswd

# SSH configuration
RUN echo "PermitRootLogin no" >> /etc/ssh/sshd_config && \
    echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config && \
    mkdir -p /run/sshd

# Create ssh directory for user
RUN mkdir -p /home/user/.ssh && chown -R user:user /home/user/.ssh

EXPOSE 22 8080

# Start SSH and HTTP server
CMD ["/bin/bash", "-c", "/usr/sbin/sshd && python -m http.server 8080"]
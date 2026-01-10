from ssh_manager.utils.ssh_configs import parse_text_to_configs


if __name__ == "__main__":
    print(parse_text_to_configs("""
Host machine-56b1e3d8
    HostName 127.0.0.1
    User root
    Port 22
    # This is not a standard SSH config
    Password None
    # localhost:8000 -> remote's localhost:80
    LocalForward 8000 localhost:80
    # Through host to reach target
    ProxyJump jump-machine-host
    """))
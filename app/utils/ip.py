import socket

def get_local_ip():
    """
    Returns the local network IP address of the machine.
    """
    try:
        # Create a dummy socket to find the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't actually connect, just used to get local interface IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

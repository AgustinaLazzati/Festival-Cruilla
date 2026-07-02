import os
import uuid
from pathlib import Path

import paramiko
from dotenv import load_dotenv
from loguru import logger
from scp import SCPClient

load_dotenv()

SSH_JUMP_SERVER_IP = os.environ["SSH_JUMP_SERVER_IP"]
SSH_JUMP_SERVER_PORT = int(os.environ["SSH_JUMP_SERVER_PORT"])
SSH_JUMP_SERVER_USER = os.environ["SSH_JUMP_SERVER_USER"]
SSH_JUMP_SERVER_PWD = os.environ["SSH_JUMP_SERVER_PWD"]

SSH_IMAGES_SERVER_IP = os.environ["SSH_IMAGES_SERVER_IP"]
SSH_IMAGES_SERVER_PORT = int(os.environ["SSH_IMAGES_SERVER_PORT"])
SSH_IMAGES_SERVER_USER = os.environ["SSH_IMAGES_SERVER_USER"]
SSH_IMAGES_SERVER_PWD = os.environ["SSH_IMAGES_SERVER_PWD"]

SERVER_ROOT_PATH = os.environ["SERVER_ROOT_PATH"]
SERVER_PUBLIC_URL = os.environ["SERVER_PUBLIC_URL"]


def upload_results(file: Path, prefix: str) -> str:
    target_filename = f"{prefix}{uuid.uuid4().hex}{file.suffix}"
    target_file_path = SERVER_ROOT_PATH.format(target_filename)

    # Create SSH tunnel
    jump_ssh = paramiko.SSHClient()
    jump_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    jump_ssh.connect(
        hostname=SSH_JUMP_SERVER_IP,
        port=SSH_JUMP_SERVER_PORT,
        username=SSH_JUMP_SERVER_USER,
        password=SSH_JUMP_SERVER_PWD,
    )
    transport = jump_ssh.get_transport()
    channel = transport.open_channel(
        "direct-tcpip",
        (SSH_IMAGES_SERVER_IP, SSH_IMAGES_SERVER_PORT),
        ("127.0.0.1", 0),
    )

    # Connect to the images storage server through SSH
    target_ssh = paramiko.SSHClient()
    target_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    target_ssh.connect(
        hostname=SSH_IMAGES_SERVER_IP,
        port=SSH_IMAGES_SERVER_PORT,
        username=SSH_IMAGES_SERVER_USER,
        password=SSH_IMAGES_SERVER_PWD,
        sock=channel,
    )

    try:
        # Upload file
        with SCPClient(target_ssh.get_transport()) as scp:
            scp.put(str(file), target_file_path)

        # Change permissions
        cmd = f"chmod 644 {target_file_path}"
        _, stdout, stderr = target_ssh.exec_command(cmd)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            logger.error(f"Failed to set permissions on image server: "
                         f"{stderr.read().decode()}")
    finally:
        target_ssh.close()
        jump_ssh.close()

    return SERVER_PUBLIC_URL.format(target_filename)

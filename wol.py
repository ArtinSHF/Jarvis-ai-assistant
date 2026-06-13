"""
wol.py — Wake-on-LAN sender
Sends a magic packet to wake your PC from sleep.
Called by the phone via the server.
"""

import socket
import struct

def send_magic_packet(mac_address: str, broadcast: str = '255.255.255.255', port: int = 9):
    """
    Send a Wake-on-LAN magic packet.
    mac_address: PC MAC address e.g. 'AA:BB:CC:DD:EE:FF'
    """
    # Clean MAC address
    mac = mac_address.replace(':', '').replace('-', '').replace('.', '').upper()
    if len(mac) != 12:
        raise ValueError(f"Invalid MAC address: {mac_address}")

    # Build magic packet: 6 bytes of 0xFF + MAC address repeated 16 times
    raw_mac = bytes.fromhex(mac)
    packet  = b'\xff' * 6 + raw_mac * 16

    # Send via UDP broadcast
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(packet, (broadcast, port))

    print(f"[WOL] Magic packet sent to {mac_address}")
    return True

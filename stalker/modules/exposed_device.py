#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exposed Device Search — identifikasi perangkat yang terekspos (tanpa API key).

Sumber keyless: Shodan InternetDB (ports/hostnames/vulns/cpes per IP).
Lalu dipetakan ke jenis perangkat berdasar port + CPE:
  kamera/DVR, router, IoT, SCADA/industri, database, web server, dll.
Plus tautan manual ke Shodan/ZoomEye/Censys web UI.
"""

from __future__ import annotations

from typing import Dict, List

from .ip_tracker import check_shodan_free

# Port → (service, device_hint)
PORT_HINTS: Dict[int, tuple] = {
    21: ("FTP", "file server"),
    22: ("SSH", "server/device (SSH)"),
    23: ("Telnet", "router/IoT (telnet, sering lemah)"),
    25: ("SMTP", "mail server"),
    53: ("DNS", "DNS server"),
    80: ("HTTP", "web server / device web UI"),
    102: ("Siemens S7", "SCADA/PLC industri"),
    110: ("POP3", "mail server"),
    143: ("IMAP", "mail server"),
    443: ("HTTPS", "web server / device web UI"),
    445: ("SMB", "Windows/file share"),
    502: ("Modbus", "SCADA/PLC industri"),
    554: ("RTSP", "KAMERA CCTV / media stream"),
    993: ("IMAPS", "mail server"),
    995: ("POP3S", "mail server"),
    1883: ("MQTT", "IoT (MQTT)"),
    1911: ("Niagara Fox", "building automation / BMS"),
    2323: ("Telnet-alt", "router/IoT"),
    2375: ("Docker", "docker daemon terekspos"),
    3306: ("MySQL", "database"),
    3389: ("RDP", "Windows remote desktop"),
    37777: ("Dahua", "DVR/NVR CCTV"),
    47808: ("BACnet", "building automation / BMS"),
    44818: ("EtherNet/IP", "SCADA/industri"),
    5432: ("PostgreSQL", "database"),
    5900: ("VNC", "remote desktop"),
    6379: ("Redis", "database/cache"),
    7547: ("TR-069", "router CPE (CWMP)"),
    8080: ("HTTP-alt", "web server / device web UI"),
    8443: ("HTTPS-alt", "web server / device web UI"),
    8554: ("RTSP-alt", "KAMERA CCTV"),
    9200: ("Elasticsearch", "database (sering bocor data)"),
    9300: ("Elasticsearch", "database (cluster)"),
    27017: ("MongoDB", "database (sering bocor data)"),
    11211: ("Memcached", "cache"),
}

CPE_HINTS = [
    ("camera", "KAMERA CCTV"), ("dvr", "DVR/NVR CCTV"), ("nvr", "DVR/NVR CCTV"),
    ("router", "router"), ("switch", "network switch"),
    ("scada", "SCADA"), ("plc", "PLC industri"), ("hmi", "HMI industri"),
    ("printer", "printer"), ("nas", "NAS/storage"),
    ("android", "perangkat Android"), ("ios", "perangkat Apple/iOS"),
    ("windows", "Windows"), ("linux", "Linux"),
    ("apache", "web server"), ("nginx", "web server"), ("iis", "web server"),
]


def _guess_device(ports: List[int], cpes: List[str]) -> Dict:
    device_type = "unknown"
    services: List[str] = []
    hints: List[str] = []

    for p in ports:
        if p in PORT_HINTS:
            svc, hint = PORT_HINTS[p]
            services.append(f"{p}/{svc}")
            hints.append(hint)

    for cpe in cpes:
        low = cpe.lower()
        for key, label in CPE_HINTS:
            if key in low:
                hints.append(label)
                break

    if any("KAMERA" in h or "DVR" in h for h in hints):
        device_type = "camera/dvr"
    elif any("SCADA" in h or "PLC" in h or "industri" in h or "BMS" in h for h in hints):
        device_type = "industrial/scada"
    elif any("router" in h for h in hints):
        device_type = "router/network"
    elif any("IoT" in h for h in hints):
        device_type = "iot"
    elif any("database" in h for h in hints):
        device_type = "database"
    elif any("web server" in h for h in hints):
        device_type = "web-server"
    elif any("printer" in h for h in hints):
        device_type = "printer"

    return {"device_type": device_type, "services": services, "hints": list(dict.fromkeys(hints))}


async def scan_device(ip: str) -> Dict:
    """Scan an IP for exposed services & guess device type (keyless)."""
    shodan = await check_shodan_free(ip)
    ports = shodan.get("open_ports", [])
    cpes = shodan.get("cpes", [])
    hostnames = shodan.get("hostnames", [])
    vulns = shodan.get("vulns", [])
    guess = _guess_device(ports, cpes)

    return {
        "ip": ip,
        "open_ports": ports,
        "hostnames": hostnames,
        "cpes": cpes[:20],
        "vulns": vulns,
        "device_type": guess["device_type"],
        "services": guess["services"],
        "hints": guess["hints"],
        "note": shodan.get("note"),
        "links": {
            "shodan": f"https://www.shodan.io/host/{ip}",
            "zoomeye": f"https://www.zoomeye.org/searchResult?q=ip%3A%22{ip}%22",
            "censys": f"https://search.censys.io/hosts/{ip}",
        },
    }


def summary(res: Dict) -> Dict:
    return {
        "ip": res.get("ip"),
        "device_type": res.get("device_type"),
        "open_ports": len(res.get("open_ports", [])),
        "vulns": len(res.get("vulns", [])),
    }

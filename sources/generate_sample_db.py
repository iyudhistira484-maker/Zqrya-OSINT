#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate SAMPLE local databases (SIAK/NPWP) for testing NIK/NKK lookup.

⚠️ SEMUA DATA DI SINI FIKTIF — nama acak, NIK acak (struktur valid), tidak
berhubungan dengan orang sungguhan. Hanya untuk menguji pipeline, bukan data
kependudukan asli.

Cara pakai:
    python sources/generate_sample_db.py [n_rows] [output_dir]
    # default: 100 baris ke databaselocal/ (di dalam project)
"""

from __future__ import annotations

import csv
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Nama depan/akhir Indonesia (fiktif untuk sample)
FIRST = ["Agus", "Budi", "Cahya", "Dewi", "Eka", "Fitri", "Gunawan", "Hesti",
         "Indra", "Joko", "Kartika", "Lukman", "Maya", "Nur", "Oki", "Putri",
         "Rizky", "Sari", "Teguh", "Umi", "Vina", "Wawan", "Yuni", "Zainal"]
LAST = ["Pratama", "Santoso", "Wijaya", "Lestari", "Hidayat", "Kusuma",
        "Saputra", "Utami", "Rahayu", "Setiawan", "Nugroho", "Handayani",
        "Permata", "Anggraini", "Maulana", "Safitri", "Ramadhan", "Putra"]

KAB_CODES = ["3523", "3510", "3578", "3273", "3171", "1371", "7371", "6471",
             "1271", "1671"]  # Tuban, Banyuwangi, Surabaya, Bandung, dll


def _random_nik() -> str:
    """NIK acak struktur valid: 6 digit wilayah + DDMMYY + 4 digit serial = 16."""
    kab = random.choice(KAB_CODES)
    kec = random.randint(1, 99)  # 2 digit kode kecamatan
    d = random.randint(1, 28)
    m = random.randint(1, 12)
    y = random.randint(1960, 2005)
    if random.random() < 0.5:  # perempuan: tanggal + 40
        d += 40
    return f"{kab}{kec:02d}{d:02d}{m:02d}{y % 100:02d}{random.randint(1, 9999):04d}"


def _random_nkk() -> str:
    """NKK acak struktur valid: 6 digit wilayah + tanggal terbit + serial."""
    kab = random.choice(KAB_CODES)
    kec = random.randint(1, 99)
    d = random.randint(1, 28)
    m = random.randint(1, 12)
    y = random.randint(1995, 2024)
    return f"{kab}{kec:02d}{d:02d}{m:02d}{y % 100:02d}{random.randint(1, 9999):04d}"


def _name() -> str:
    return f"{random.choice(FIRST)} {random.choice(LAST)}"


def _date_between(start_y: int, end_y: int) -> str:
    start = datetime(start_y, 1, 1)
    end = datetime(end_y, 12, 31)
    delta = (end - start).days
    return (start + timedelta(days=random.randint(0, delta))).strftime("%Y-%m-%d")


def _siak_row(nkk: str, head: bool = False) -> Dict[str, str]:
    """Satu baris SIAK fiktif. head=True → kepala keluarga (kawin, lebih tua)."""
    married = random.random() < 0.55 or head
    if head:
        status = "K"
        y = random.randint(1960, 1985)
        gender = "1" if random.random() < 0.6 else "2"
    else:
        status = random.choices(["K", "BK", "C"], weights=[40, 50, 10])[0]
        y = random.randint(1985, 2005)
        gender = "1" if random.random() < 0.5 else "2"
    return {
        "NKK": nkk,
        "NIK": _random_nik(),
        "NAMA_LGKP": _name(),
        "TMPT_LHR": random.choice(["Surabaya", "Tuban", "Jakarta", "Bandung", "Medan"]),
        "TGL_LHR": _date_between(y, y + 5),
        "JENIS_KLMIN": gender,
        "AGAMA": random.choice(["ISLAM", "KRISTEN", "KATHOLIK", "HINDU", "BUDHA"]),
        "STAT_KWN": status,
        "PDDK_AKH": random.choice(["SD", "SMP", "SMA", "SMK", "D3", "S1", "S2"]),
        "JENIS_PKRJN": random.choice(["WIRASWASTA", "PETANI", "PNS", "KARYAWAN SWASTA", "IRT", "BURUH", "GURU"]),
        "EMAIL": f"user{random.randint(1,999999)}@example.com",
        "SMS_PHONE": f"08{random.randint(10,99)}{random.randint(1000000,9999999)}",
    }


def main(n: int = 100, out_dir: str = "") -> None:
    out = Path(out_dir) if out_dir else PROJECT_ROOT / "databaselocal"
    out.mkdir(parents=True, exist_ok=True)

    # ── SIAK (siak_full_sample_1k.csv) ──
    # Buat sebagian baris berbagi NKK (keluarga 2–4 anggota) supaya fitur
    # NKK menampilkan list keluarga. Kepala keluarga = kawin (K).
    siak_fields = ["NKK", "NIK", "NAMA_LGKP", "TMPT_LHR", "TGL_LHR", "JENIS_KLMIN",
                   "AGAMA", "STAT_KWN", "PDDK_AKH", "JENIS_PKRJN", "EMAIL", "SMS_PHONE"]
    rows: List[Dict[str, str]] = []
    i = 0
    while i < n:
        nkk = _random_nkk()
        # ~40% baris jadi bagian dari keluarga 2–4 orang
        if random.random() < 0.4 and i + 3 < n:
            fam_size = random.randint(2, 4)
            for j in range(fam_size):
                rows.append(_siak_row(nkk, head=(j == 0)))
            i += fam_size
        else:
            rows.append(_siak_row(nkk, head=True))
            i += 1

    with open(out / "siak_full_sample_1k.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=siak_fields)
        w.writeheader()
        w.writerows(rows)

    # ── NPWP (npwp-10k-sample.csv) ──
    npwp_fields = ["NIK", "NAMA", "NPWP", "ALAMAT", "KELURAHAN", "KABKOT", "PROVINSI", "TELP", "EMAIL", "TTL"]
    with open(out / "npwp-10k-sample.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=npwp_fields)
        w.writeheader()
        for i in range(n):
            w.writerow({
                "NIK": _random_nik(),
                "NAMA": _name(),
                "NPWP": f"{random.randint(10,99)}.{random.randint(100,999)}.{random.randint(100,999)}.{random.randint(1,9)}-{random.randint(100,999)}.000",
                "ALAMAT": f"Jl. {random.choice(['Merdeka','Sudirman','Ahmad Yani','Diponegoro'])} No. {random.randint(1,200)}",
                "KELURAHAN": random.choice(["Karangrejo", "Sumberejo", "Kebonsari", "Banyuurip"]),
                "KABKOT": random.choice(["Tuban", "Surabaya", "Banyuwangi", "Bandung"]),
                "PROVINSI": random.choice(["Jawa Timur", "Jawa Barat", "DKI Jakarta"]),
                "TELP": f"031{random.randint(1000000,9999999)}",
                "EMAIL": f"npwp{i}@example.com",
                "TTL": f"{random.choice(['Surabaya','Tuban','Jakarta'])}, {_date_between(1960, 2000)}",
            })

    print(f"Sampel ditulis ke: {out}")
    print(f"  siak_full_sample_1k.csv  — {n} baris (NKK + NIK + status kawin)")
    print(f"  npwp-10k-sample.csv      — {n} baris (NIK + NPWP)")
    print()
    print("⚠ Data 100% FIKTIF (nama & nomor acak). Untuk data nyata,")
    print("  letakkan CSV SIAK/NPWP asli di folder yang sama dengan format kolom di atas.")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    out = sys.argv[2] if len(sys.argv) > 2 else ""
    main(n, out)

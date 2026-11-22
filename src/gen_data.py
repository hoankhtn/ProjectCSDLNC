#!/usr/bin/env python3
"""
CSDLNC-17 - Sinh dữ liệu lớn cho FitLife Hub (SQL Server).

Bảng trong 01_schema.sql : HANG_HOI_VIEN, CHI_NHANH, NHAN_VIEN, SAN_PHAM, GOI_DICH_VU,
                           HOI_VIEN, TON_KHO, HOA_DON, CHI_TIET_HOA_DON, LICH_SU_DIEM
Bảng bổ sung (02_extra_tables.sql): LICH_HEN_PT, CHECK_IN

Cách chạy:
  pip install faker pandas numpy pyodbc
  python gen_data.py --out ./data                       # chỉ xuất CSV (kiểm tra nhanh)
  python gen_data.py --out ./data --conn "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=TenDatabase;Trusted_Connection=yes;TrustServerCertificate=yes"
  python gen_data.py --scale 0.1                        # chạy thử 10% quy mô
"""
import argparse
import os
import time
import unicodedata

import numpy as np
import pandas as pd
from faker import Faker

SEED = 42
DATA_START = np.datetime64("2025-01-01", "D")     # đầu khoảng dữ liệu giao dịch
DATA_END = np.datetime64("2026-11-20", "D")       # cuối khoảng dữ liệu "quá khứ"
BOOKING_END = np.datetime64("2026-12-15", "D")    # lịch hẹn PT có cả lịch tương lai
REG_START = np.datetime64("2023-01-01", "D")
REG_END = np.datetime64("2026-11-15", "D")
CURRENT_YEAR = 2026                                # năm xét hạng (TongChiTieuNam)
POINT_UNIT = 100_000                               # 1 điểm = 100.000 VNĐ

N_BRANCH = 12
PT_PER_BR, LT_PER_BR, QL_PER_BR, BH_PER_BR = 4, 2, 1, 3

HOURS = np.arange(6, 22)
# Trọng số giờ: cao điểm 17-20h
HOUR_W = np.array([4, 6, 6, 4, 3, 3, 4, 5, 6, 8, 12, 16, 16, 14, 9, 5], dtype=float)
HOUR_W /= HOUR_W.sum()


# ----------------------------------------------------------------- helpers
def slug(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def rand_dt(rng, days, hour_w=HOUR_W):
    """days: datetime64[D] -> datetime64[s] với giờ phút giây ngẫu nhiên."""
    n = len(days)
    h = rng.choice(HOURS, size=n, p=hour_w)
    sec = h * 3600 + rng.integers(0, 3600, n)
    return days.astype("datetime64[s]") + sec.astype("timedelta64[s]")


def fmt(prefix, arr, width):
    return prefix + pd.Series(arr).astype(str).str.zfill(width)


# --------------------------------------------------------------- generators
def gen_catalog(rng, fake):
    hang = pd.DataFrame({
        "MaHang": ["H01", "H02", "H03"],
        "TenHang": ["Silver", "Gold", "Platinum"],
        # Đề bài chưa nêu ngưỡng -> giả định, có thể chỉnh
        "NguongChiTieuToiThieu": [5_000_000, 15_000_000, 40_000_000],
    })

    districts = ["Quận 1", "Quận 3", "Quận 5", "Quận 7", "Quận 10", "Bình Thạnh",
                 "Phú Nhuận", "Tân Bình", "Gò Vấp", "Thủ Đức", "Bình Tân", "Tân Phú"]
    cn = pd.DataFrame({"MaCN": [f"CN{i:02d}" for i in range(1, N_BRANCH + 1)],
                       "TenCN": [f"FitLife Hub {d}" for d in districts]})

    rows = []
    for ci, ma_cn in enumerate(cn.MaCN):
        for role, k in (("PT", PT_PER_BR), ("LT", LT_PER_BR), ("QL", QL_PER_BR), ("BH", BH_PER_BR)):
            for j in range(k):
                rows.append((f"{role}{ci + 1:02d}{j + 1:02d}", fake.name(), role, ma_cn))
    nv_full = pd.DataFrame(rows, columns=["MaNV", "TenNV", "Role", "MaCN"])
    nv = nv_full[["MaNV", "TenNV"]].copy()          # đúng cột của bảng NHAN_VIEN trong SQL

    spec = [("Whey Protein", "Thực phẩm bổ sung", (550_000, 1_800_000)),
            ("BCAA", "Thực phẩm bổ sung", (300_000, 700_000)),
            ("Creatine", "Thực phẩm bổ sung", (350_000, 800_000)),
            ("Pre-workout", "Thực phẩm bổ sung", (400_000, 900_000)),
            ("Thanh protein", "Thực phẩm bổ sung", (25_000, 60_000)),
            ("Bình nước", "Phụ kiện", (80_000, 250_000)),
            ("Thảm yoga", "Phụ kiện", (200_000, 600_000)),
            ("Găng tay tập", "Phụ kiện", (100_000, 300_000)),
            ("Dây kháng lực", "Phụ kiện", (90_000, 350_000)),
            ("Khăn thể thao", "Phụ kiện", (50_000, 150_000))]
    sp = []
    for i in range(40):
        name, loai, (lo, hi) = spec[i % len(spec)]
        price = int(round(rng.integers(lo, hi + 1) / 1000) * 1000)
        sp.append((f"SP{i + 1:03d}", f"{name} mẫu {i // len(spec) + 1}", loai, price,
                   int(rng.integers(5, 30))))
    sp = pd.DataFrame(sp, columns=["MaSP", "TenSP", "Loai", "GiaBan", "MucTonToiThieu"])

    base = {"Gym": 500_000, "Yoga": 700_000, "GroupX": 600_000, "Spa": 400_000, "Sauna": 300_000}
    factor = {1: 1.0, 3: 0.9, 6: 0.8, 12: 0.7}
    goi = []
    k = 1
    for loai, b in base.items():
        for m, f in factor.items():
            goi.append((f"G{k:03d}", f"{loai} {m} tháng", loai, m, 0, int(round(b * m * f / 1000) * 1000)))
            k += 1
    for m, f in factor.items():                      # PT 1-1: 4 buổi/tháng
        buoi = 4 * m
        goi.append((f"G{k:03d}", f"PT 1-1 {buoi} buổi ({m} tháng)", "PT 1-1", m, buoi,
                    int(round(300_000 * buoi * f / 1000) * 1000)))
        k += 1
    goi = pd.DataFrame(goi, columns=["MaGoi", "TenGoi", "Loai", "ThoiHanThang", "SoBuoiPT", "GiaTien"])

    tk = pd.MultiIndex.from_product([cn.MaCN, sp.MaSP], names=["MaCN", "MaSP"]).to_frame(index=False)
    tk["SoLuongTon"] = rng.integers(0, 200, len(tk))
    return hang, cn, nv, nv_full, sp, goi, tk


def gen_members(rng, fake, n):
    reg = REG_START + rng.integers(0, int((REG_END - REG_START).astype(int)) + 1, n).astype("timedelta64[D]")
    prefixes = np.array([90, 91, 93, 97, 98, 86, 88, 89, 70, 79, 77])
    idx = rng.choice(len(prefixes) * 10 ** 7, n, replace=False)          # SDT duy nhất
    sdt = "0" + pd.Series(prefixes[idx // 10 ** 7]).astype(str) + \
          pd.Series(idx % 10 ** 7).astype(str).str.zfill(7)
    cccd = "0" + pd.Series(rng.integers(1, 97, n)).astype(str).str.zfill(2) + \
           pd.Series(rng.choice(10 ** 9, n, replace=False)).astype(str).str.zfill(9)
    names = [fake.name() for _ in range(n)]
    email = [f"{slug(nm)}{i}@example.com" if rng.random() > 0.1 else None for i, nm in enumerate(names)]
    birth = np.datetime64("1966-01-01", "D") + rng.integers(0, 365 * 43, n).astype("timedelta64[D]")
    hv = pd.DataFrame({
        "MaHV": fmt("HV", np.arange(1, n + 1), 7),
        "HoTen": names, "SDT": sdt.values, "Email": email, "CCCD": cccd.values,
        "GioiTinh": rng.choice(["Nam", "Nữ"], n, p=[0.52, 0.48]),
        "NgaySinh": pd.to_datetime(birth).date,
        "NgayDangKy": pd.to_datetime(reg).date,
    })
    return hv, reg


def gen_invoices(rng, n_hd, n_hv, reg, nv_full, sp, goi):
    has_mem = rng.random(n_hd) < 0.80                                   # 20% khách lẻ
    mem = np.where(has_mem, (rng.random(n_hd) ** 1.5 * n_hv).astype(int), -1)

    lo = np.where(has_mem, np.maximum(reg[np.clip(mem, 0, None)], DATA_START), DATA_START)
    span = (DATA_END - lo).astype(int) + 1
    day = lo + (rng.random(n_hd) * span).astype(int).astype("timedelta64[D]")
    ts = rand_dt(rng, day)
    order = np.argsort(ts, kind="stable")                               # mã tăng theo thời gian
    has_mem, mem, ts = has_mem[order], mem[order], ts[order]

    cn_idx = rng.choice(N_BRANCH, n_hd, p=np.random.default_rng(1).dirichlet(np.ones(N_BRANCH) * 20))
    bh = [nv_full[(nv_full.Role == "BH") & (nv_full.MaCN == f"CN{c + 1:02d}")].MaNV.values
          for c in range(N_BRANCH)]
    ma_nv = np.empty(n_hd, dtype=object)
    for c in range(N_BRANCH):
        m = cn_idx == c
        ma_nv[m] = rng.choice(bh[c], m.sum())

    hd = pd.DataFrame({
        "MaHD": fmt("HD", np.arange(1, n_hd + 1), 8),
        "NgayLap": ts,
        "MaCN": [f"CN{c + 1:02d}" for c in cn_idx],
        "MaNV": ma_nv,
        "MaHV": np.where(has_mem, "HV" + pd.Series(mem + 1).astype(str).str.zfill(7), None),
    })

    # ---- chi tiết
    n_lines = rng.choice([1, 2, 3], n_hd, p=[0.5, 0.35, 0.15])
    total = n_lines.sum()
    hd_idx = np.repeat(np.arange(n_hd), n_lines)
    starts = np.cumsum(n_lines) - n_lines
    dong = np.arange(total) - np.repeat(starts, n_lines) + 1

    is_goi = (rng.random(total) < 0.45) & has_mem[hd_idx]               # khách lẻ chỉ mua sản phẩm
    gi = rng.integers(0, len(goi), total)
    si = rng.integers(0, len(sp), total)
    qty = np.where(is_goi, 1, rng.choice([1, 2, 3], total, p=[0.7, 0.2, 0.1]))
    price = np.where(is_goi, goi.GiaTien.values[gi], sp.GiaBan.values[si]).astype(np.int64)

    ct = pd.DataFrame({
        "MaHD": hd.MaHD.values[hd_idx],
        "Dong": dong,
        "MaGoi": np.where(is_goi, goi.MaGoi.values[gi], None),
        "MaSP": np.where(is_goi, None, sp.MaSP.values[si]),
        "SoLuong": qty,
        "DonGia": price,
        "ThanhTien": qty * price,
        "NgayLap": ts[hd_idx],
    })

    tong = np.bincount(hd_idx, weights=ct.ThanhTien.values, minlength=n_hd).astype(np.int64)
    pct = rng.choice([5, 10, 15], n_hd)
    giam = np.where(has_mem & (rng.random(n_hd) < 0.25), (tong * pct // 100 // 1000) * 1000, 0)
    hd["TongTien"] = tong
    hd["GiamGia"] = giam
    hd["HinhThucTT"] = rng.choice(["Tiền mặt", "VNPay", "Thẻ"], n_hd, p=[0.40, 0.35, 0.25])
    return hd, ct, mem


def gen_loyalty(hd, mem, hang, n_hv):
    paid = (hd.TongTien - hd.GiamGia).values
    is_mem = mem >= 0
    this_year = pd.DatetimeIndex(hd.NgayLap).year.values == CURRENT_YEAR
    spend = np.bincount(mem[is_mem & this_year], weights=paid[is_mem & this_year],
                        minlength=n_hv).astype(np.int64)
    pts = paid // POINT_UNIT
    keep = is_mem & (pts > 0)
    diem = np.bincount(mem[keep], weights=pts[keep], minlength=n_hv).astype(np.int64)

    thr = hang.NguongChiTieuToiThieu.values
    ma = hang.MaHang.values
    hv_hang = np.select([spend >= thr[2], spend >= thr[1], spend >= thr[0]], [ma[2], ma[1], ma[0]], None)

    ls = pd.DataFrame({
        "MaLS": fmt("LS", np.arange(1, keep.sum() + 1), 8),
        "MaHV": hd.MaHV.values[keep],
        "MaHD": hd.MaHD.values[keep],
        "DiemCong": pts[keep],
        "ThoiDiem": hd.NgayLap.values[keep],
    })
    return spend, diem, hv_hang, ls


def gen_bookings(rng, n, n_hv, reg, nv_full):
    pt = nv_full[nv_full.Role == "PT"].reset_index(drop=True)
    n_days = int((BOOKING_END - DATA_START).astype(int)) + 1
    n_slot = len(HOURS) - 1                                             # giờ bắt đầu 6..20 (kết thúc <= 22h)
    s = rng.choice(len(pt) * n_days * n_slot, n, replace=False)         # slot (PT,ngày,giờ) duy nhất => không trùng lịch PT
    pi, rem = s // (n_days * n_slot), s % (n_days * n_slot)
    day = DATA_START + (rem // n_slot).astype("timedelta64[D]")
    start = day.astype("datetime64[s]") + ((HOURS[rem % n_slot]) * 3600).astype("timedelta64[s]")

    m = rng.integers(0, n_hv, n)                                        # hội viên phải đăng ký trước ngày hẹn
    for _ in range(30):
        bad = reg[m] > day
        if not bad.any():
            break
        m[bad] = rng.integers(0, n_hv, bad.sum())
    bad = reg[m] > day
    m[bad] = 0
    day_ok = np.where(bad, np.maximum(day, reg[0]), day)  # (an toàn, thực tế không xảy ra)
    assert (reg[m] <= day_ok).all()

    past = day <= DATA_END
    status = np.where(past, rng.choice(["Đã hoàn thành", "Đã hủy"], n, p=[0.80, 0.20]),
                      rng.choice(["Đã đặt", "Đã hủy"], n, p=[0.92, 0.08]))
    created = np.maximum(start - (rng.integers(1, 15, n) * 86400 + rng.integers(0, 86400, n)).astype("timedelta64[s]"),
                         reg[m].astype("datetime64[s]"))
    order = np.argsort(start, kind="stable")
    lh = pd.DataFrame({
        "MaLichHen": fmt("LH", np.arange(1, n + 1), 8),
        "MaHV": ("HV" + pd.Series(m[order] + 1).astype(str).str.zfill(7)).values,
        "MaPT": pt.MaNV.values[pi[order]],
        "MaCN": pt.MaCN.values[pi[order]],
        "ThoiGianBatDau": start[order],
        "ThoiGianKetThuc": start[order] + np.timedelta64(3600, "s"),
        "TrangThai": status[order],
        "NgayTao": created[order],
    })
    return lh


def gen_checkins(rng, n, n_hv, reg):
    home = rng.integers(0, N_BRANCH, n_hv)
    m = (rng.random(n) ** 1.3 * n_hv).astype(int)                       # hội viên chăm tập check-in nhiều hơn
    lo = np.maximum(reg[m], DATA_START)
    span = (DATA_END - lo).astype(int) + 1
    day = lo + (rng.random(n) * span).astype(int).astype("timedelta64[D]")
    t_in = rand_dt(rng, day)
    ok = rng.random(n) > 0.04                                           # ~4% bị từ chối
    cn = np.where(rng.random(n) < 0.9, home[m], rng.integers(0, N_BRANCH, n))
    dur = rng.integers(30, 151, n) * 60
    order = np.argsort(t_in, kind="stable")
    m, t_in, ok, cn, dur = m[order], t_in[order], ok[order], cn[order], dur[order]

    reasons = rng.choice(["Gói tập hết hạn", "Không có quyền tại chi nhánh", "Mã QR không hợp lệ"], n)
    yc = rng.permutation(n) + 1                                         # MaYeuCau duy nhất
    ci = pd.DataFrame({
        "MaCheckIn": fmt("CI", np.arange(1, n + 1), 8),
        "MaYeuCau": fmt("YC", yc, 10),
        "MaHV": "HV" + pd.Series(m + 1).astype(str).str.zfill(7),
        "MaCN": [f"CN{c + 1:02d}" for c in cn],
        "MaThietBi": [f"CN{c + 1:02d}-D{d}" for c, d in zip(cn, rng.integers(1, 4, n))],
        "ThoiGianVao": np.where(ok, t_in, np.datetime64("NaT", "s")),
        "ThoiGianRa": np.where(ok, t_in + dur.astype("timedelta64[s]"), np.datetime64("NaT", "s")),
        "KetQuaXacThuc": np.where(ok, "Thành công", "Từ chối"),
        "LyDoTuChoi": np.where(ok, None, reasons),
        "ThoiGianGhiNhan": t_in,
    })
    return ci


# ------------------------------------------------------------------- checks
def verify(t):
    hv, hd, ct, ls, lh, ci = (t[k] for k in ("HOI_VIEN", "HOA_DON", "CHI_TIET_HOA_DON",
                                              "LICH_SU_DIEM", "LICH_HEN_PT", "CHECK_IN"))
    assert hv.MaHV.is_unique and hv.SDT.is_unique
    assert hd.MaHD.is_unique and not ct.duplicated(["MaHD", "Dong"]).any()
    assert (ct.ThanhTien == ct.SoLuong * ct.DonGia).all()
    assert ((ct.MaGoi.notna()) ^ (ct.MaSP.notna())).all()
    assert (hd.GiamGia <= hd.TongTien).all()
    assert (ct.groupby("MaHD").ThanhTien.sum().reindex(hd.MaHD).values == hd.TongTien.values).all()
    assert hd.MaHV.dropna().isin(hv.MaHV).all() and ls.MaHD.isin(hd.MaHD).all()
    reg = hv.set_index("MaHV").NgayDangKy.astype("datetime64[ns]")
    m = hd.dropna(subset=["MaHV"])
    assert (pd.to_datetime(m.NgayLap).dt.normalize().values >= reg.reindex(m.MaHV).values).all()
    assert not lh.duplicated(["MaPT", "ThoiGianBatDau"]).any()
    assert (lh.ThoiGianBatDau < lh.ThoiGianKetThuc).all()
    assert ci.MaYeuCau.is_unique
    ok = ci.ThoiGianRa.notna()
    assert (ci.ThoiGianRa[ok] >= ci.ThoiGianVao[ok]).all()
    cr = ci.dropna(subset=["ThoiGianVao"])
    assert (pd.to_datetime(cr.ThoiGianVao).dt.normalize().values >= reg.reindex(cr.MaHV).values).all()
    print("OK - mọi kiểm tra ràng buộc đều đạt.")


# ------------------------------------------------------------------ loading
LOAD_ORDER = ["HANG_HOI_VIEN", "CHI_NHANH", "NHAN_VIEN", "SAN_PHAM", "GOI_DICH_VU", "HOI_VIEN",
              "TON_KHO", "HOA_DON", "CHI_TIET_HOA_DON", "LICH_SU_DIEM", "LICH_HEN_PT", "CHECK_IN"]


def to_rows(df):
    obj = df.astype(object)
    obj = obj.where(df.notna(), None)
    for c in df.columns:
        if str(df[c].dtype).startswith("datetime64"):
            obj[c] = [None if pd.isna(v) else v.to_pydatetime() for v in df[c]]
    return list(obj.itertuples(index=False, name=None))


def load_sql(tables, conn_str, batch=50_000):
    import pyodbc
    cn = pyodbc.connect(conn_str, autocommit=False)
    cur = cn.cursor()
    cur.fast_executemany = True
    for name in reversed(LOAD_ORDER):                                    # xóa dữ liệu cũ đúng thứ tự FK
        cur.execute(f"DELETE FROM {name}")
    cn.commit()
    for name in LOAD_ORDER:
        df = tables[name]
        sql = f"INSERT INTO {name} ({','.join(df.columns)}) VALUES ({','.join('?' * len(df.columns))})"
        rows = to_rows(df)
        for i in range(0, len(rows), batch):
            cur.executemany(sql, rows[i:i + batch])
        cn.commit()
        print(f"  loaded {name:<18} {len(rows):>8,}")
    cn.close()


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="./data")
    ap.add_argument("--conn", help="pyodbc connection string; bỏ trống = chỉ ghi CSV")
    ap.add_argument("--scale", type=float, default=1.0, help="hệ số quy mô (0.1 = 10%%)")
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    fake = Faker("vi_VN")
    Faker.seed(a.seed)
    n_hv, n_hd = int(100_000 * a.scale), int(150_000 * a.scale)
    n_lh, n_ci = int(100_000 * a.scale), int(350_000 * a.scale)

    t0 = time.time()
    hang, cn, nv, nv_full, sp, goi, tk = gen_catalog(rng, fake)
    hv, reg = gen_members(rng, fake, n_hv)
    hd, ct, mem = gen_invoices(rng, n_hd, n_hv, reg, nv_full, sp, goi)
    spend, diem, hv_hang, ls = gen_loyalty(hd, mem, hang, n_hv)
    hv["TongChiTieuNam"], hv["DiemLoyalty"], hv["MaHang"] = spend, diem, hv_hang
    lh = gen_bookings(rng, n_lh, n_hv, reg, nv_full)
    ci = gen_checkins(rng, n_ci, n_hv, reg)

    tables = {"HANG_HOI_VIEN": hang, "CHI_NHANH": cn, "NHAN_VIEN": nv, "SAN_PHAM": sp,
              "GOI_DICH_VU": goi, "HOI_VIEN": hv, "TON_KHO": tk, "HOA_DON": hd,
              "CHI_TIET_HOA_DON": ct, "LICH_SU_DIEM": ls, "LICH_HEN_PT": lh, "CHECK_IN": ci}
    verify(tables)

    os.makedirs(a.out, exist_ok=True)
    for name in LOAD_ORDER:
        tables[name].to_csv(os.path.join(a.out, f"{name}.csv"), index=False, encoding="utf-8-sig")
        print(f"  {name:<18} {len(tables[name]):>8,} dòng")
    print(f"Sinh dữ liệu xong trong {time.time() - t0:.1f}s -> {a.out}")

    if a.conn:
        load_sql(tables, a.conn)


if __name__ == "__main__":
    main()
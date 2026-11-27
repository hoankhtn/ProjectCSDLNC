USE TenDatabase;
GO

-- 0. XOA BANG CU 

DROP TABLE IF EXISTS dbo.CHI_NHANH;
DROP TABLE IF EXISTS dbo.CHI_TIET_HOA_HONG;
DROP TABLE IF EXISTS dbo.BANG_LUONG_THANG;
DROP TABLE IF EXISTS dbo.HOA_HONG_PT;
DROP TABLE IF EXISTS dbo.LICH_SU_LUONG;
DROP TABLE IF EXISTS dbo.LICH_SU_CONG_TAC;
DROP TABLE IF EXISTS dbo.NHAN_VIEN;
GO


-- 1. CHI_NHANH
-- Luu thong tin cac chi nhanh cua phong gym.

CREATE TABLE dbo.CHI_NHANH (
    MaCN         VARCHAR(10)   NOT NULL,
    TenCN        NVARCHAR(100) NOT NULL,
    DiaChi       NVARCHAR(255) NOT NULL,
    SDT          VARCHAR(15)   NOT NULL,
    GioMoCua     TIME          NOT NULL,
    GioDongCua   TIME          NOT NULL,

    CONSTRAINT PK_CHI_NHANH
        PRIMARY KEY (MaCN),

    CONSTRAINT UQ_CHI_NHANH_SDT
        UNIQUE (SDT)
);
GO


-- 2. NHAN_VIEN
-- Ho so nhan vien hien tai.

CREATE TABLE dbo.NHAN_VIEN (
    MaNV         VARCHAR(10)   NOT NULL,
    MaCN         VARCHAR(10)   NOT NULL,
    HoTen        NVARCHAR(100) NOT NULL,   
    SDT          VARCHAR(15)   NOT NULL,
    ChucVu       VARCHAR(50)   NOT NULL,
    LuongCoBan   DECIMAL(18,2) NOT NULL,
    NgayVaoLam   DATE          NOT NULL,
    TrangThai    VARCHAR(20)   NOT NULL CONSTRAINT DF_NHAN_VIEN_TRANGTHAI DEFAULT 'Dang lam',

    CONSTRAINT PK_NHAN_VIEN PRIMARY KEY (MaNV),
    CONSTRAINT UQ_NHAN_VIEN_SDT UNIQUE (SDT),

    CONSTRAINT FK_NHAN_VIEN_CHI_NHANH
        FOREIGN KEY (MaCN) REFERENCES dbo.CHI_NHANH(MaCN),

    CONSTRAINT CK_NHAN_VIEN_LUONG
        CHECK (LuongCoBan > 0),

    CONSTRAINT CK_NHAN_VIEN_CHUCVU
        CHECK (ChucVu IN (
            'PT',
            'Le tan',
            'Quan ly chi nhanh',
            'Nhan vien ban hang'
        )),

    CONSTRAINT CK_NHAN_VIEN_TRANGTHAI
        CHECK (TrangThai IN ('Dang lam', 'Nghi viec'))
);
GO

CREATE INDEX IX_NHAN_VIEN_MACN   ON dbo.NHAN_VIEN (MaCN);
CREATE INDEX IX_NHAN_VIEN_CHUCVU ON dbo.NHAN_VIEN (ChucVu);
GO


-- 3. LICH_SU_CONG_TAC
-- Theo doi cac giai doan cong tac / dieu chuyen cua nhan vien.
-- PK: (MaNV, NgayBatDau)
-- NgayKetThuc = NULL: giai doan hien tai.
-- Moi nhan vien chi co toi da 1 giai doan dang mo: dung filtered unique index


CREATE TABLE dbo.LICH_SU_CONG_TAC (
    MaNV          VARCHAR(10) NOT NULL,
    NgayBatDau    DATE        NOT NULL,
    MaCN          VARCHAR(10) NOT NULL,
    ChucVu        VARCHAR(50) NOT NULL,
    NgayKetThuc   DATE        NULL,

    CONSTRAINT PK_LICH_SU_CONG_TAC
        PRIMARY KEY (MaNV, NgayBatDau),

    CONSTRAINT FK_LSCT_NHAN_VIEN
        FOREIGN KEY (MaNV) REFERENCES dbo.NHAN_VIEN(MaNV),

    CONSTRAINT FK_LSCT_CHI_NHANH
        FOREIGN KEY (MaCN) REFERENCES dbo.CHI_NHANH(MaCN),

    CONSTRAINT CK_LSCT_NGAY
        CHECK (NgayKetThuc IS NULL OR NgayKetThuc >= NgayBatDau),

    CONSTRAINT CK_LSCT_CHUCVU
        CHECK (ChucVu IN (
            'PT',
            'Le tan',
            'Quan ly chi nhanh',
            'Nhan vien ban hang'
        ))
);
GO

CREATE INDEX IX_LSCT_MACN ON dbo.LICH_SU_CONG_TAC (MaCN);
CREATE INDEX IX_LSCT_THOIGIAN ON dbo.LICH_SU_CONG_TAC (MaNV, NgayBatDau, NgayKetThuc);

-- Thay cho UQ_LSCT_MOT_GIAI_DOAN_MO + cot MaNV_GiaiDoanMo
CREATE UNIQUE INDEX UQ_LSCT_MOT_GIAI_DOAN_MO
    ON dbo.LICH_SU_CONG_TAC (MaNV)
    WHERE NgayKetThuc IS NULL;
GO


-- 4. LICH_SU_LUONG
-- Luu lich su thay doi luong co ban, khong ghi de lich su cu.
-- PK: (MaNV, NgayHieuLuc)

CREATE TABLE dbo.LICH_SU_LUONG (
    MaNV             VARCHAR(10)   NOT NULL,
    NgayHieuLuc      DATE          NOT NULL,
    MucLuong         DECIMAL(18,2) NOT NULL,
    NgayHetHieuLuc   DATE          NULL,

    CONSTRAINT PK_LICH_SU_LUONG
        PRIMARY KEY (MaNV, NgayHieuLuc),

    CONSTRAINT FK_LSL_NHAN_VIEN
        FOREIGN KEY (MaNV) REFERENCES dbo.NHAN_VIEN(MaNV),

    CONSTRAINT CK_LSL_MUCLUONG
        CHECK (MucLuong > 0),

    CONSTRAINT CK_LSL_NGAY
        CHECK (NgayHetHieuLuc IS NULL OR NgayHetHieuLuc >= NgayHieuLuc)
);
GO

CREATE INDEX IX_LSL_THOIGIAN ON dbo.LICH_SU_LUONG (MaNV, NgayHieuLuc, NgayHetHieuLuc);
GO


-- 5. HOA_HONG_PT
-- Luu cac phien ban chinh sach hoa hong PT.

CREATE TABLE dbo.HOA_HONG_PT (
    MaChinhSach       VARCHAR(10)   NOT NULL,
    MucHoaHongBuoi    DECIMAL(18,2) NOT NULL,
    NgayHieuLuc       DATE          NOT NULL,
    NgayHetHieuLuc    DATE          NULL,

    CONSTRAINT PK_HOA_HONG_PT
        PRIMARY KEY (MaChinhSach),

    CONSTRAINT CK_HHPT_MUC
        CHECK (MucHoaHongBuoi > 0),

    CONSTRAINT CK_HHPT_NGAY
        CHECK (NgayHetHieuLuc IS NULL OR NgayHetHieuLuc >= NgayHieuLuc)
);
GO

CREATE INDEX IX_HHPT_NGAYHIEULUC ON dbo.HOA_HONG_PT (NgayHieuLuc, NgayHetHieuLuc);
GO


-- 6. BANG_LUONG_THANG
-- Moi nhan vien co toi da mot bang luong trong mot thang/nam.
-- TongThucLanh = LuongCoBan + TongHoaHong.

CREATE TABLE dbo.BANG_LUONG_THANG (
    MaNV           VARCHAR(10)   NOT NULL,
    Thang          TINYINT       NOT NULL,  
    Nam            SMALLINT      NOT NULL,
    LuongCoBan     DECIMAL(18,2) NOT NULL,
    TongHoaHong    DECIMAL(18,2) NOT NULL CONSTRAINT DF_BLT_TONGHOAHONG DEFAULT 0,
    TongThucLanh   DECIMAL(18,2) NOT NULL,

    CONSTRAINT PK_BANG_LUONG_THANG
        PRIMARY KEY (MaNV, Thang, Nam),

    CONSTRAINT FK_BLT_NHAN_VIEN
        FOREIGN KEY (MaNV) REFERENCES dbo.NHAN_VIEN(MaNV),

    CONSTRAINT CK_BLT_THANG
        CHECK (Thang BETWEEN 1 AND 12),

    CONSTRAINT CK_BLT_NAM
        CHECK (Nam >= 2000),

    CONSTRAINT CK_BLT_LUONG
        CHECK (LuongCoBan > 0),

    CONSTRAINT CK_BLT_HOAHONG
        CHECK (TongHoaHong >= 0),

    CONSTRAINT CK_BLT_THUCLANH
        CHECK (
            TongThucLanh >= 0
            AND TongThucLanh = LuongCoBan + TongHoaHong
        )
);
GO

CREATE INDEX IX_BLT_NAM_THANG ON dbo.BANG_LUONG_THANG (Nam, Thang);
GO


-- 7. CHI_TIET_HOA_HONG
-- Tong hop hoa hong theo nhan vien, thang, nam, chi nhanh
-- va chinh sach ap dung.
--
-- Dua MaChinhSach vao PK de phan biet truong hop mot nhan vien
-- co nhieu chinh sach hoa hong trong cung thang tai mot chi nhanh.

CREATE TABLE dbo.CHI_TIET_HOA_HONG (
    MaNV           VARCHAR(10)   NOT NULL,
    Thang          TINYINT       NOT NULL,
    Nam            SMALLINT      NOT NULL,
    MaCN           VARCHAR(10)   NOT NULL,
    MaChinhSach    VARCHAR(10)   NOT NULL,
    SoBuoi         INT           NOT NULL CONSTRAINT DF_CTHH_SOBUOI DEFAULT 0,
    DonGia         DECIMAL(18,2) NOT NULL,
    ThanhTien      DECIMAL(18,2) NOT NULL,

    CONSTRAINT PK_CHI_TIET_HOA_HONG
        PRIMARY KEY (MaNV, Thang, Nam, MaCN, MaChinhSach),

    CONSTRAINT FK_CTHH_BANG_LUONG
        FOREIGN KEY (MaNV, Thang, Nam)
        REFERENCES dbo.BANG_LUONG_THANG(MaNV, Thang, Nam),

    CONSTRAINT FK_CTHH_CHI_NHANH
        FOREIGN KEY (MaCN) REFERENCES dbo.CHI_NHANH(MaCN),

    CONSTRAINT FK_CTHH_CHINHSACH
        FOREIGN KEY (MaChinhSach)
        REFERENCES dbo.HOA_HONG_PT(MaChinhSach),

    CONSTRAINT CK_CTHH_THANG
        CHECK (Thang BETWEEN 1 AND 12),

    CONSTRAINT CK_CTHH_NAM
        CHECK (Nam >= 2000),

    CONSTRAINT CK_CTHH_SOBUOI
        CHECK (SoBuoi >= 0),              

    CONSTRAINT CK_CTHH_DONGIA
        CHECK (DonGia > 0),

    CONSTRAINT CK_CTHH_THANHTIEN
        CHECK (ThanhTien = SoBuoi * DonGia)
);
GO

CREATE INDEX IX_CTHH_CHINHANH  ON dbo.CHI_TIET_HOA_HONG (MaCN);
CREATE INDEX IX_CTHH_CHINHSACH ON dbo.CHI_TIET_HOA_HONG (MaChinhSach);
CREATE INDEX IX_CTHH_KYLUONG   ON dbo.CHI_TIET_HOA_HONG (Nam, Thang, MaNV);
GO

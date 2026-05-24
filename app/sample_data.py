"""Sample data — mirrors the prototype so the demo is consistent."""
from .reconciliation import Invoice, BankTxn

SAMPLE_INVOICES = [
    Invoice("INV-2041", "Shenzhen Components Ltd", 12480.0, "USD", "PO-88120", "2026-05-02"),
    Invoice("INV-2042", "Lmisbah Logistics", 3250.0, "EUR", "PO-88121", "2026-05-03"),
    Invoice("INV-2043", "Aurora Design Studio", 8800.0, "GBP", "PO-88122", "2026-05-05"),
    Invoice("INV-2044", "Shenzhen Components Ltd", 12480.0, "USD", "PO-88120", "2026-05-06"),
    Invoice("INV-2045", "Nordic Cloud Hosting", 990.0, "EUR", "PO-88124", "2026-05-08"),
    Invoice("INV-2046", "Quartz Marketing FZE", 15600.0, "USD", "", "2026-05-10"),
]

SAMPLE_TXNS = [
    BankTxn("TXN-9912", "WIRE OUT - SHENZHEN COMPONENTS", 12480.0, "USD", "PO-88120", "2026-05-04"),
    BankTxn("TXN-9913", "SEPA - LISBAH LOGISTIK", 3187.5, "EUR", "PO-88121", "2026-05-05"),
    BankTxn("TXN-9914", "FX PAYMENT - AURORA DESIGN", 8800.0, "GBP", "PO-88122", "2026-05-07"),
    BankTxn("TXN-9915", "DIRECT DEBIT - NORDIC CLOUD", 990.0, "EUR", "PO-88124", "2026-05-09"),
    BankTxn("TXN-9916", "WIRE OUT - QUARTZ MKTG", 15600.0, "USD", "", "2026-05-11"),
    BankTxn("TXN-9917", "CARD - UNKNOWN MERCHANT 4471", 2150.0, "USD", "", "2026-05-12"),
]

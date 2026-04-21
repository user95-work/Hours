from datetime import date

def get_scotland_bank_holidays():
    return {
        date(2026, 1, 1),   # Thursday 01.01.26
        date(2026, 1, 2),   # Friday 02.01.26
        date(2026, 4, 6),   # Monday 06.04.26
        date(2026, 5, 4),   # Monday 04.05.26
        date(2026, 7, 20),  # Monday 20.07.26
        date(2026, 9, 28),  # Monday 28.09.26
        date(2026, 12, 25), # Friday 25.12.26
        date(2026, 12, 26), # Saturday 26.12.26
    }
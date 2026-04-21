import requests
from datetime import datetime,date

URL = "https://www.gov.uk/bank-holidays.json"
_cache = None

def _load_data():
    global _cache
    if _cache is None:
        response = requests.get(URL)
        response.raise_for_status()
        _cache = response.json()
    return _cache



def get_all_bank_holidays(region="england-and-wales"):
    data = _load_data()
    events = data[region]["events"]

    return {
        datetime.strptime(e["date"], "%Y-%m-%d").date()
        for e in events
    }



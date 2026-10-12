"""Build data_england/england_ids.json: Gateway councils minus Scotland/Wales/NI minus already-harvested."""
import json
import re
from pathlib import Path

BASE = Path(__file__).parent
DONE = {9, 10, 74, 170, 172, 173, 182, 191, 201, 208, 209, 217, 233, 238, 263}

SCOTLAND = ["Aberdeen City", "Aberdeenshire", "Angus", "Argyll and Bute", "City of Edinburgh",
            "Edinburgh", "Clackmannanshire", "Comhairle nan Eilean Siar", "Na h-Eileanan Siar",
            "Western Isles", "Dumfries and Galloway", "Dundee City", "East Ayrshire",
            "East Dunbartonshire", "East Lothian", "East Renfrewshire", "Falkirk", "Fife",
            "Glasgow City", "Glasgow", "Highland", "Inverclyde", "Midlothian", "Moray",
            "North Ayrshire", "North Lanarkshire", "Orkney Islands", "Perth and Kinross",
            "Renfrewshire", "Scottish Borders", "Shetland Islands", "South Ayrshire",
            "South Lanarkshire", "Stirling", "West Dunbartonshire", "West Lothian"]
WALES = ["Blaenau Gwent", "Bridgend", "Caerphilly", "Cardiff", "Carmarthenshire", "Ceredigion",
         "Conwy", "Denbighshire", "Flintshire", "Gwynedd", "Isle of Anglesey", "Anglesey",
         "Merthyr Tydfil", "Monmouthshire", "Neath Port Talbot", "Newport", "Pembrokeshire",
         "Powys", "Rhondda Cynon Taf", "Swansea", "Torfaen", "Vale of Glamorgan", "Wrexham"]
NI = ["Antrim and Newtownabbey", "Ards and North Down", "Armagh City Banbridge and Craigavon",
      "Belfast", "Causeway Coast and Glens", "Derry City and Strabane", "Fermanagh and Omagh",
      "Lisburn and Castlereagh", "Mid and East Antrim", "Mid Ulster", "Newry Mourne and Down"]


def norm(s):
    s = s.lower().replace("&", "and")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", s)).strip()


CELTIC = {norm(n) for n in SCOTLAND + WALES + NI}

councils = json.load(open(BASE / "data" / "_all_councils.json", encoding="utf-8"))
england, dropped = [], []
for c in councils:
    n = norm(c["name"])
    if n in CELTIC or any(n == cel or n.startswith(cel + " ") or cel.startswith(n + " ") for cel in CELTIC):
        dropped.append(c["name"])
    elif c["id"] in DONE:
        pass
    else:
        england.append(c)

out = BASE / "data_england"
out.mkdir(exist_ok=True)
json.dump([c["id"] for c in england], open(out / "england_ids.json", "w"), indent=0)
json.dump({c["id"]: c["name"] for c in england}, open(out / "england_names.json", "w"), indent=1)

print(f"total {len(councils)} | dropped celtic {len(dropped)} | already done {len(DONE)} | to harvest {len(england)}")
print("\nDROPPED:", "; ".join(sorted(dropped)))
print("\nTO HARVEST:", "; ".join(sorted(c["name"] for c in england)))

"""Shaun's preferred price-compare corridor: Hilliard Rome Rd, Hilliard/Columbus OH.

All four chains have a store on (or immediately off) this corridor, so every
comparison — in-app or via live chat checks — uses these locations.
"""
STORES = {
    "Kroger": {
        "address": "2525 Hilliard Rome Rd, Hilliard, OH 43026",
        # Kroger API locationId for the Hilliard-Rome store (verified via API).
        "location_id": "01600867",
    },
    "Meijer": {
        "address": "1661 Hilliard Rome Rd, Columbus, OH",
        "store_no": "104",
    },
    "Aldi": {
        "address": "1786 Hilliard Rome Rd, Hilliard, OH 43026",
    },
    "Walmart": {
        # Not literally addressed on Hilliard Rome Rd: sits at the NE corner
        # of Hilliard-Rome Rd & Trabue Rd, same corridor.
        "address": "5200 Westpointe Plaza Dr, Columbus, OH 43228",
        "store_no": "2426",
    },
}

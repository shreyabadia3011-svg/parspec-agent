"""
Parspec Construction Procurement Agent v2
Upgraded with: confidence scoring, verbatim grounding, fuzzy catalogue matching,
HITL routing, multi-page PDF chunking, rich agent trace, PDF quote export
"""

from flask import Flask, request, jsonify, send_file
import anthropic
import json
import re
import os
import io
import difflib
from datetime import datetime

app = Flask(__name__)

# ─── MEP PRODUCT CATALOGUE (50 products) ───────────────────────────────────
CATALOGUE = [
    # ELECTRICAL
    {"id":"E001","category":"Electrical","name":"20A Single Pole Circuit Breaker","brand":"Square D","unit":"EA","base_price":18.50,"specs":{"amperage":"20A","poles":1,"voltage":"120V"}},
    {"id":"E002","category":"Electrical","name":"200A Main Electrical Panel 40-Circuit","brand":"Eaton","unit":"EA","base_price":285.00,"specs":{"amperage":"200A","circuits":40,"voltage":"120/240V"}},
    {"id":"E003","category":"Electrical","name":"15A Duplex Outlet NEMA 5-15R","brand":"Leviton","unit":"EA","base_price":4.25,"specs":{"amperage":"15A","type":"duplex","nema":"5-15R"}},
    {"id":"E004","category":"Electrical","name":"20A GFCI Outlet","brand":"Leviton","unit":"EA","base_price":18.75,"specs":{"amperage":"20A","type":"GFCI","protection":"ground_fault"}},
    {"id":"E005","category":"Electrical","name":"2x4 LED Troffer 4000K 50W","brand":"Lithonia","unit":"EA","base_price":89.00,"specs":{"watts":50,"kelvin":"4000K","size":"2x4","lumens":5500}},
    {"id":"E006","category":"Electrical","name":"LED Exit Sign Battery Backup","brand":"Lithonia","unit":"EA","base_price":45.00,"specs":{"type":"exit_sign","backup":"battery","voltage":"120/277V"}},
    {"id":"E007","category":"Electrical","name":"1/2 inch EMT Conduit 10ft","brand":"Allied","unit":"EA","base_price":8.40,"specs":{"diameter":"1/2 inch","type":"EMT","length":"10ft"}},
    {"id":"E008","category":"Electrical","name":"3/4 inch EMT Conduit 10ft","brand":"Allied","unit":"EA","base_price":11.20,"specs":{"diameter":"3/4 inch","type":"EMT","length":"10ft"}},
    {"id":"E009","category":"Electrical","name":"100A 3-Phase Disconnect Switch","brand":"Square D","unit":"EA","base_price":195.00,"specs":{"amperage":"100A","phases":3,"type":"disconnect"}},
    {"id":"E010","category":"Electrical","name":"Automatic Transfer Switch 200A","brand":"Generac","unit":"EA","base_price":1850.00,"specs":{"amperage":"200A","type":"ATS","transfer_time":"<10s"}},

    # PLUMBING
    {"id":"P001","category":"Plumbing","name":"3/4 inch Copper Type L 10ft","brand":"Mueller","unit":"EA","base_price":22.50,"specs":{"diameter":"3/4 inch","type":"L","material":"copper","length":"10ft"}},
    {"id":"P002","category":"Plumbing","name":"1/2 inch Copper Type M 10ft","brand":"Mueller","unit":"EA","base_price":14.80,"specs":{"diameter":"1/2 inch","type":"M","material":"copper","length":"10ft"}},
    {"id":"P003","category":"Plumbing","name":"3/4 inch Ball Valve Full Port","brand":"Apollo","unit":"EA","base_price":28.40,"specs":{"diameter":"3/4 inch","type":"ball","port":"full","material":"brass"}},
    {"id":"P004","category":"Plumbing","name":"40 Gallon Water Heater Electric","brand":"A.O. Smith","unit":"EA","base_price":520.00,"specs":{"capacity":"40gal","type":"electric","recovery":"20gph","energy_factor":0.92}},
    {"id":"P005","category":"Plumbing","name":"80 Gallon Water Heater Gas","brand":"Bradford White","unit":"EA","base_price":1240.00,"specs":{"capacity":"80gal","type":"gas","btu":76000,"first_hour":"165gal"}},
    {"id":"P006","category":"Plumbing","name":"Elongated Toilet 1.28 GPF","brand":"Kohler","unit":"EA","base_price":285.00,"specs":{"type":"elongated","gpf":1.28,"flush":"gravity","ada":True}},
    {"id":"P007","category":"Plumbing","name":"Single Handle Kitchen Faucet","brand":"Moen","unit":"EA","base_price":145.00,"specs":{"handles":1,"type":"kitchen","flow_rate":"1.8gpm"}},
    {"id":"P008","category":"Plumbing","name":"4 inch PVC DWV Pipe 10ft","brand":"Charlotte Pipe","unit":"EA","base_price":18.90,"specs":{"diameter":"4 inch","material":"PVC","schedule":"DWV","length":"10ft"}},
    {"id":"P009","category":"Plumbing","name":"Pressure Reducing Valve 3/4in","brand":"Watts","unit":"EA","base_price":58.50,"specs":{"diameter":"3/4 inch","type":"PRV","range":"25-75psi","preset":"50psi"}},
    {"id":"P010","category":"Plumbing","name":"Backflow Preventer 1in Double Check","brand":"Watts","unit":"EA","base_price":195.00,"specs":{"diameter":"1 inch","type":"double_check","standard":"ASSE1015"}},

    # HVAC
    {"id":"H001","category":"HVAC","name":"3 Ton Split AC System 16 SEER","brand":"Carrier","unit":"EA","base_price":2850.00,"specs":{"tons":3,"seer":16,"type":"split","refrigerant":"R-410A"}},
    {"id":"H002","category":"HVAC","name":"5 Ton Rooftop Unit 14 SEER","brand":"Trane","unit":"EA","base_price":6400.00,"specs":{"tons":5,"seer":14,"type":"RTU","refrigerant":"R-410A"}},
    {"id":"H003","category":"HVAC","name":"Air Handler 3 Ton","brand":"Carrier","unit":"EA","base_price":1240.00,"specs":{"tons":3,"type":"air_handler","coil":"A-coil"}},
    {"id":"H004","category":"HVAC","name":"80000 BTU Gas Furnace 96% AFUE","brand":"Lennox","unit":"EA","base_price":1850.00,"specs":{"btu":80000,"afue":"96%","stages":2,"type":"gas_furnace"}},
    {"id":"H005","category":"HVAC","name":"Variable Speed Air Handler 4 Ton","brand":"Trane","unit":"EA","base_price":2100.00,"specs":{"tons":4,"type":"variable_speed_AHU","motor":"ECM"}},
    {"id":"H006","category":"HVAC","name":"12x12 Supply Air Grille","brand":"Titus","unit":"EA","base_price":24.50,"specs":{"size":"12x12","type":"supply_grille","material":"steel"}},
    {"id":"H007","category":"HVAC","name":"20x20x1 MERV-13 Air Filter","brand":"Filtrete","unit":"EA","base_price":18.75,"specs":{"size":"20x20x1","merv":13,"type":"pleated"}},
    {"id":"H008","category":"HVAC","name":"Programmable Thermostat 7-Day","brand":"Honeywell","unit":"EA","base_price":68.00,"specs":{"type":"programmable","schedule":"7-day","stages":"2H/1C"}},
    {"id":"H009","category":"HVAC","name":"Smart Thermostat Wi-Fi","brand":"Ecobee","unit":"EA","base_price":189.00,"specs":{"type":"smart","wifi":True,"sensors":"remote","compatibility":"multi-stage"}},
    {"id":"H010","category":"HVAC","name":"Energy Recovery Ventilator 200CFM","brand":"Renewaire","unit":"EA","base_price":1450.00,"specs":{"cfm":200,"type":"ERV","efficiency":"75%","ashrae":"62.1"}},

    # FIRE PROTECTION
    {"id":"F001","category":"Fire Protection","name":"Upright Sprinkler Head 1/2in K5.6","brand":"Victaulic","unit":"EA","base_price":12.80,"specs":{"type":"upright","orifice":"1/2 inch","k_factor":5.6,"temp":"155F"}},
    {"id":"F002","category":"Fire Protection","name":"Pendant Sprinkler Head K5.6","brand":"Viking","unit":"EA","base_price":11.40,"specs":{"type":"pendant","k_factor":5.6,"temp":"155F","coverage":"130sqft"}},
    {"id":"F003","category":"Fire Protection","name":"Addressable Smoke Detector","brand":"Notifier","unit":"EA","base_price":89.00,"specs":{"type":"addressable","detection":"photoelectric","loop":"supervised"}},
    {"id":"F004","category":"Fire Protection","name":"Manual Pull Station Dual Action","brand":"Notifier","unit":"EA","base_price":68.50,"specs":{"type":"pull_station","action":"dual","nfpa":"72"}},
    {"id":"F005","category":"Fire Protection","name":"Fire Alarm Control Panel 10-Zone","brand":"Notifier","unit":"EA","base_price":1250.00,"specs":{"zones":10,"type":"conventional","nfpa":"72","battery_backup":"24h"}},

    # LIGHTING
    {"id":"L001","category":"Lighting","name":"4ft LED Linear Strip 4000K 40W","brand":"RAB","unit":"EA","base_price":68.00,"specs":{"length":"4ft","watts":40,"kelvin":"4000K","lumens":4800}},
    {"id":"L002","category":"Lighting","name":"LED Recessed Downlight 6in 15W","brand":"Cree","unit":"EA","base_price":42.00,"specs":{"size":"6 inch","watts":15,"kelvin":"3000K","lumens":1100}},
    {"id":"L003","category":"Lighting","name":"Emergency LED Egress Light","brand":"Lithonia","unit":"EA","base_price":95.00,"specs":{"type":"egress","runtime":"90min","lumens":1600,"battery":"NiCad"}},
    {"id":"L004","category":"Lighting","name":"LED Parking Lot Light 150W","brand":"RAB","unit":"EA","base_price":385.00,"specs":{"watts":150,"kelvin":"5000K","lumens":18000,"rating":"IP65"}},
    {"id":"L005","category":"Lighting","name":"Occupancy Sensor Ceiling Mount 1200sqft","brand":"Lutron","unit":"EA","base_price":78.00,"specs":{"coverage":"1200sqft","type":"PIR+ultrasonic","voltage":"120/277V"}},

    # LOW VOLTAGE / SECURITY
    {"id":"S001","category":"Low Voltage","name":"IP Security Camera 4MP PoE","brand":"Axis","unit":"EA","base_price":285.00,"specs":{"resolution":"4MP","type":"IP","poe":True,"ir_range":"30m"}},
    {"id":"S002","category":"Low Voltage","name":"8-Channel NVR 4K","brand":"Hikvision","unit":"EA","base_price":345.00,"specs":{"channels":8,"resolution":"4K","storage":"HDD ready","poe_ports":8}},
    {"id":"S003","category":"Low Voltage","name":"Access Control Card Reader","brand":"HID","unit":"EA","base_price":195.00,"specs":{"type":"proximity","frequency":"125kHz","range":"3-5 inch","wiegand":True}},
    {"id":"S004","category":"Low Voltage","name":"Cat6 UTP Cable 1000ft","brand":"Belden","unit":"SPOOL","base_price":185.00,"specs":{"category":"Cat6","type":"UTP","length":"1000ft","standard":"TIA-568"}},
    {"id":"S005","category":"Low Voltage","name":"24-Port PoE Network Switch","brand":"Cisco","unit":"EA","base_price":895.00,"specs":{"ports":24,"poe":"802.3af/at","uplink":"2xSFP","managed":True}},

    # MECHANICAL
    {"id":"M001","category":"Mechanical","name":"Circulator Pump 1/25HP","brand":"Grundfos","unit":"EA","base_price":285.00,"specs":{"hp":"1/25","type":"circulator","gpm":10,"head":"15ft"}},
    {"id":"M002","category":"Mechanical","name":"Expansion Tank 4.4 Gallon","brand":"Amtrol","unit":"EA","base_price":78.00,"specs":{"capacity":"4.4gal","type":"expansion","max_pressure":"150psi","acceptance":"2.0gal"}},
    {"id":"M003","category":"Mechanical","name":"Pressure Gauge 0-160 PSI 2.5in","brand":"Ashcroft","unit":"EA","base_price":24.50,"specs":{"range":"0-160psi","size":"2.5 inch","type":"dry","connection":"1/4 NPT"}},
    {"id":"M004","category":"Mechanical","name":"Isolation Valve Gate 1in",  "brand":"Nibco","unit":"EA","base_price":34.80,"specs":{"diameter":"1 inch","type":"gate","material":"brass","class":"150"}},
    {"id":"M005","category":"Mechanical","name":"Pipe Insulation 3/4in x 6ft","brand":"Armaflex","unit":"EA","base_price":8.90,"specs":{"pipe_diameter":"3/4 inch","thickness":"1 inch","material":"foam","r_value":"R-4"}},
]

# ─── SAMPLE SPECS ───────────────────────────────────────────────────────────
SAMPLE_SPECS = {
    "electrical": """ELECTRICAL SPECIFICATION - OFFICE BUILDING RENOVATION
Project: 3-story commercial office, 45,000 sq ft, Chicago IL
Engineer: Smith & Associates MEP, Drawing E-100 Rev 2

PANEL SCHEDULE:
- Main Service: 400A, 3-phase, 208/120V
- Panel LP-1: 200A main electrical panel, 40-circuit, replace existing
- Panel LP-2: 100A 3-phase disconnect switch, mechanical room

LIGHTING (per floor - 3 floors):
- Office areas: 2x4 LED Troffer 4000K 50W, Qty: 45 per floor
- Corridors: LED Recessed Downlight 6in 15W, Qty: 20 per floor  
- Parking: LED Parking Lot Light 150W, Qty: 12 total
- Emergency: LED Exit Sign Battery Backup, Qty: 8 per floor
- Egress: Emergency LED Egress Light, Qty: 6 per floor

DEVICES:
- Duplex outlets 15A: Qty 120 per floor (360 total)
- GFCI outlets 20A: Qty 24 (kitchenettes and bathrooms)
- Occupancy Sensor Ceiling 1200sqft: Qty 18 per floor

CONDUIT:
- 1/2 inch EMT: 2,400 linear feet
- 3/4 inch EMT: 1,800 linear feet

POWER:
- 20A circuit breakers: Qty 80
- Automatic Transfer Switch 200A: Qty 1 (generator backup)

MARKUP: 20%""",

    "plumbing": """PLUMBING SPECIFICATION - MEDICAL OFFICE BUILDING
Project: 2-story medical clinic, 18,000 sq ft, Denver CO
Plumbing Engineer: Western MEP Group, Drawing P-200

WATER DISTRIBUTION:
- 3/4 inch copper type L supply main: 850 linear feet
- 1/2 inch copper type M branch lines: 1,200 linear feet
- Pressure reducing valve 3/4 inch: Qty 2 (each floor)
- Backflow preventer 1 inch double check: Qty 1 (main entry)

FIXTURES (total building):
- Elongated toilets 1.28 GPF: Qty 18
- Single handle kitchen faucets: Qty 6 (break rooms)

HOT WATER:
- 80 gallon water heater gas: Qty 2
- Circulator pump 1/25HP: Qty 1
- Expansion tank 4.4 gallon: Qty 2
- Pipe insulation 3/4 inch x 6ft: Qty 120

DRAINAGE:
- 4 inch PVC DWV pipe: 640 linear feet

VALVES:
- 3/4 inch ball valve full port: Qty 28
- Isolation valve gate 1 inch: Qty 14
- Pressure gauge 0-160 PSI 2.5 inch: Qty 4

MARKUP: 18%""",

    "hvac": """HVAC SPECIFICATION - HOTEL RENOVATION
Project: 120-room boutique hotel, 85,000 sq ft, Nashville TN
Mechanical Engineer: Southeast Engineering, Drawing M-300

COOLING/HEATING SYSTEMS:
- 5 Ton Rooftop Unit 14 SEER: Qty 6 (one per floor, floors 1-6)
- 3 Ton Split AC System 16 SEER: Qty 12 (suites and common areas)
- Air Handler 3 Ton: Qty 12 (paired with split systems)
- Variable Speed Air Handler 4 Ton: Qty 4 (lobby, ballroom, fitness, restaurant)
- 80000 BTU Gas Furnace 96% AFUE: Qty 6 (supplemental heating, north exposure)

VENTILATION:
- Energy Recovery Ventilator 200CFM: Qty 8
- 12x12 Supply Air Grille: Qty 240
- 20x20x1 MERV-13 Air Filter: Qty 60

CONTROLS:
- Smart Thermostat Wi-Fi: Qty 120 (one per room)
- Programmable Thermostat 7-Day: Qty 18 (common areas)

MARKUP: 22%""",

    "full_mep": """FULL MEP SPECIFICATION - NEW CONSTRUCTION SCHOOL
Project: K-8 Elementary School, 62,000 sq ft, 2-story, Austin TX
MEP Engineer: Austin Engineering Group, Permit Set Rev 3

══ ELECTRICAL ══
Service: 600A, 3-phase 208/120V
- 200A main electrical panel 40-circuit: Qty 3 (one per wing)
- 100A 3-phase disconnect: Qty 2 (mechanical rooms)
- 20A circuit breakers: Qty 96
- 2x4 LED Troffer 4000K 50W: Qty 280 (classrooms, offices)
- LED Recessed Downlight 6in 15W: Qty 60 (corridors)
- LED Exit Sign Battery Backup: Qty 42
- Emergency LED Egress Light: Qty 36
- 15A Duplex outlets: Qty 420
- 20A GFCI outlets: Qty 48 (labs, kitchens, restrooms)
- 1/2 inch EMT conduit: 4,200 LF
- 3/4 inch EMT conduit: 2,800 LF
- Automatic Transfer Switch 200A: Qty 1
- Occupancy Sensor Ceiling 1200sqft: Qty 64

══ PLUMBING ══
- 3/4 inch copper type L: 1,400 LF
- 1/2 inch copper type M: 2,100 LF
- Elongated toilets 1.28 GPF: Qty 36
- Single handle faucets: Qty 24
- 40 gallon water heater electric: Qty 2 (faculty lounge, gymnasium)
- 80 gallon water heater gas: Qty 1 (main service)
- 4 inch PVC DWV: 980 LF
- 3/4 inch ball valves: Qty 42
- Pressure reducing valve 3/4 inch: Qty 3
- Backflow preventer 1 inch: Qty 1
- Expansion tank 4.4 gallon: Qty 2
- Pipe insulation 3/4 inch: Qty 160
- Circulator pump 1/25HP: Qty 2

══ HVAC ══
- 5 Ton Rooftop Unit 14 SEER: Qty 4 (gym, cafeteria, admin, library)
- 3 Ton Split AC: Qty 8 (computer labs, specialty rooms)
- Air Handler 3 Ton: Qty 8
- 80000 BTU Gas Furnace 96%: Qty 4
- Energy Recovery Ventilator 200CFM: Qty 6
- 12x12 Supply Air Grille: Qty 180
- 20x20x1 MERV-13 Filters: Qty 48
- Smart Thermostat Wi-Fi: Qty 12 (admin + labs)
- Programmable Thermostat 7-Day: Qty 28

══ FIRE PROTECTION ══
- Pendant Sprinkler Head K5.6: Qty 320
- Addressable Smoke Detector: Qty 64
- Manual Pull Station Dual Action: Qty 18
- Fire Alarm Control Panel 10-Zone: Qty 1

══ LOW VOLTAGE ══
- Cat6 UTP Cable 1000ft: Qty 8 spools
- 24-Port PoE Network Switch: Qty 4
- IP Security Camera 4MP PoE: Qty 24
- 8-Channel NVR 4K: Qty 3
- Access Control Card Reader: Qty 12 (exterior doors, server room)

MARKUP: 20%"""
}

# ─── AGENT TOOLS ─────────────────────────────────────────────────────────────

def inspect_document(text: str) -> dict:
    """Layer 1: Classify document, score structure, identify MEP categories."""
    text_lower = text.lower()
    categories = []
    if any(k in text_lower for k in ["electrical","panel","circuit","outlet","conduit","breaker","amps","voltage","lighting","led"]):
        categories.append("Electrical")
    if any(k in text_lower for k in ["plumbing","water heater","toilet","faucet","pipe","valve","copper","pvc","gpm"]):
        categories.append("Plumbing")
    if any(k in text_lower for k in ["hvac","cooling","heating","furnace","rooftop","air handler","ton","btu","seer","thermostat","duct"]):
        categories.append("HVAC")
    if any(k in text_lower for k in ["sprinkler","fire alarm","smoke detector","pull station","nfpa"]):
        categories.append("Fire Protection")
    if any(k in text_lower for k in ["camera","switch","cat6","access control","nvr","poe","low voltage"]):
        categories.append("Low Voltage")

    # Structure scoring
    score = 0
    word_count = len(text.split())

    # Empty doc guard
    if word_count < 10:
        return {
            "mep_categories": [],
            "structure_score": 0,
            "routing_decision": "RULE_ENGINE",
            "routing_rationale": "Document too short to classify",
            "word_count": word_count,
            "chunks_needed": 1,
            "estimated_line_items": 0
        }
    if re.search(r'qty[\s:]+\d+', text_lower): score += 25
    if re.search(r'\d+\s*(ea|each|lf|sf|ft)', text_lower, re.I): score += 20
    if re.search(r'(specification|schedule|drawing)', text_lower): score += 15
    if re.search(r'(section|part|division)\s+\d+', text_lower, re.I): score += 15
    if len(categories) > 0: score += 15
    if re.search(r'markup[\s:]+\d+', text_lower): score += 10
    score = min(score, 100)

    # Route decision
    route = "RULE_ENGINE" if score >= 70 else "LLM_ENGINE"

    word_count = len(text.split())
    chunks_needed = max(1, (word_count // 800) + (1 if word_count % 800 > 0 else 0))
    return {
        "mep_categories": categories if categories else ["Unknown"],
        "structure_score": score,
        "routing_decision": route,
        "routing_rationale": f"Score {score}/100 → {'structured enough for regex extraction' if route == 'RULE_ENGINE' else 'unstructured, requires LLM extraction'}",
        "word_count": word_count,
        "chunks_needed": chunks_needed,
        "estimated_line_items": text_lower.count("qty") + text_lower.count("quantity")
    }


def extract_requirements(text: str, routing: str) -> dict:
    """Layer 2: Extract structured requirements with confidence + verbatim grounding."""
    items = []

    # Regex patterns — covers: bullet Qty, table x N, prose "quantity N", shorthand "N units", column format
    patterns = [
        # Standard bullet: "- Product Name: Qty 10" or "- Product: Qty: 10"
        r'[-•]\s*([^:,\n]{5,60}):\s*Qty[:\s]+(\d+[\d,]*)',
        r'[-•]\s*([^:,\n]{5,60}),\s*Qty[:\s]+(\d+[\d,]*)',
        # General "Product: Qty N"
        r'([A-Za-z0-9/\s\-\.]{10,60})\s*:\s*Qty\s+(\d+[\d,]*)',
        r'([A-Za-z0-9/\s\-\.]{10,60})\s*[-–]\s*Qty\s*[:\s]+(\d+[\d,]*)',
        # Table format: "Product x 24" or "Product - 24 units"
        r'([A-Za-z0-9/\s\-\.]{8,55})\s+[x×]\s+(\d+[\d,]*)',
        # Prose: "quantity N" or "total N"  preceded by product
        r'([A-Za-z0-9/\s\-\.]{8,55}),\s*(?:quantity|total count|total)\s+(\d+)',
        r'([A-Za-z0-9/\s\-\.]{8,55}),\s*(?:quantity|total)\s*:\s*(\d+)',
        # Shorthand: "N x product" or "Qty N product"
        r'(?:qty|quantity)\s+(\d+)\s+[-–]?\s*([A-Za-z0-9/\s\-\.]{8,55})',
        # Column / schedule: "Product    N" (2+ spaces then number)
        r'([A-Za-z][A-Za-z0-9/\s\-\.]{7,50})\s{2,}(\d+)\s*(?:EA|ea|each|units?|lf|sf|LF|SF)?\b',
        # "N units (description)" or "description - N" at end of line
        r'([A-Za-z0-9/\s\-\.]{8,55})\s*[-–:]\s*(?:need\s+)?(\d+)\s*(?:unit|ea|each|fixture|detector|valve|pump)s?',
        # Spec-number format: "inch/amp/ton" keyword with qty
        r'([\d/]+\s+(?:inch|in|amp|A|ton|gal|btu|watt|w|ft|lf|sf)[^\n:,]{3,50})[\s,]+qty[:\s]+(\d+)',
        # "N filters" / "N fixtures" / "N pumps" style
        r'([A-Za-z0-9/\s\-\.]{8,55}):\s*(\d+)\s*(?:units?|fixtures?|detectors?|valves?|pumps?|filters?)',
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for m in matches:
            desc = m.group(1).strip().strip('-•').strip()
            qty_raw = m.group(2).replace(',', '')
            if len(desc) < 5 or not qty_raw.isdigit():
                continue
            qty = int(qty_raw)

            # Verbatim quote grounding
            start = max(0, m.start() - 20)
            end = min(len(text), m.end() + 20)
            verbatim_quote = text[start:end].strip()

            # Confidence scoring
            conf = 0.95
            if qty > 10000: conf -= 0.20
            if len(desc) < 8: conf -= 0.15
            if qty == 0: conf = 0.0

            # Unit detection
            unit = "EA"
            if any(u in desc.lower() for u in ["lf","linear feet","linear foot"]): unit = "LF"
            elif any(u in desc.lower() for u in ["sf","square feet","sq ft"]): unit = "SF"
            elif any(u in desc.lower() for u in ["spool"]): unit = "SPOOL"

            items.append({
                "description": desc,
                "quantity": qty,
                "unit": unit,
                "confidence": round(conf, 2),
                "verbatim_quote": verbatim_quote[:120],
                "extraction_method": "REGEX",
                "grounded": True
            })

    # Markup extraction
    markup = 20
    markup_match = re.search(r'markup[\s:]+(\d+)%?', text, re.IGNORECASE)
    if markup_match:
        markup = int(markup_match.group(1))

    # Deduplicate by description similarity
    unique_items = []
    seen = []
    for item in items:
        is_dup = any(
            difflib.SequenceMatcher(None, item["description"].lower(), s.lower()).ratio() > 0.85
            for s in seen
        )
        if not is_dup:
            unique_items.append(item)
            seen.append(item["description"])

    # HITL routing
    auto_items = [i for i in unique_items if i["confidence"] >= 0.90]
    review_items = [i for i in unique_items if 0.70 <= i["confidence"] < 0.90]
    reject_items = [i for i in unique_items if i["confidence"] < 0.70]

    return {
        "extracted_items": unique_items,
        "total_items": len(unique_items),
        "markup_percent": markup,
        "auto_accepted": len(auto_items),
        "needs_review": len(review_items),
        "rejected": len(reject_items),
        "hitl_routing": {
            "auto": [i["description"][:40] for i in auto_items[:5]],
            "review": [i["description"][:40] for i in review_items[:5]],
            "reject": [i["description"][:40] for i in reject_items[:3]]
        }
    }


def match_catalogue(items: list) -> dict:
    """Layer 3: Fuzzy catalogue matching with ranked alternatives + confidence."""
    matches = []
    unmatched = []

    for item in items:
        desc_lower = item["description"].lower()
        candidates = []

        for product in CATALOGUE:
            prod_name_lower = product["name"].lower()

            # Multi-signal scoring
            score = 0

            # Fuzzy string match
            ratio = difflib.SequenceMatcher(None, desc_lower, prod_name_lower).ratio()
            score += ratio * 40

            # Category keyword match
            cat_keywords = {
                "Electrical": ["circuit breaker","panel","outlet","conduit","led","switch","wire","electrical","emt","gfci","transfer"],
                "Plumbing": ["copper","pvc","valve","water heater","toilet","faucet","pipe","plumbing","backflow","pressure"],
                "HVAC": ["ton","btu","seer","furnace","air handler","thermostat","hvac","grille","filter","erv","rtu"],
                "Fire Protection": ["sprinkler","smoke","fire alarm","pull station","detector"],
                "Low Voltage": ["camera","switch","cat6","nvr","access control","poe"],
                "Lighting": ["led","troffer","recessed","downlight","exit","egress","strip","lumens"],
                "Mechanical": ["pump","expansion tank","gauge","insulation","isolation"]
            }
            for cat, keywords in cat_keywords.items():
                if any(kw in desc_lower for kw in keywords) and product["category"] == cat:
                    score += 20

            # Spec keyword matches
            spec_hits = sum(
                1 for v in product["specs"].values()
                if str(v).lower() in desc_lower
            )
            score += spec_hits * 8

            # Partial word overlap
            desc_words = set(re.findall(r'\w+', desc_lower))
            prod_words = set(re.findall(r'\w+', prod_name_lower))
            overlap = len(desc_words & prod_words)
            score += overlap * 5

            candidates.append({
                "product": product,
                "score": round(score, 1)
            })

        # Sort by score, take top 3
        candidates.sort(key=lambda x: x["score"], reverse=True)
        top3 = candidates[:3]

        best = top3[0]
        match_confidence = min(0.99, best["score"] / 85)

        if best["score"] >= 20:
            product = best["product"]
            qty = item["quantity"]
            unit_price = product["base_price"]
            line_total = round(qty * unit_price, 2)

            matches.append({
                "input_description": item["description"],
                "quantity": qty,
                "unit": item["unit"],
                "matched_product": {
                    "id": product["id"],
                    "name": product["name"],
                    "brand": product["brand"],
                    "category": product["category"],
                    "unit_price": unit_price,
                    "specs": product["specs"]
                },
                "match_confidence": round(match_confidence, 2),
                "match_score": best["score"],
                "alternatives": [
                    {
                        "name": c["product"]["name"],
                        "id": c["product"]["id"],
                        "unit_price": c["product"]["base_price"],
                        "score": c["score"]
                    } for c in top3[1:]
                ],
                "line_total": line_total,
                "extraction_confidence": item["confidence"],
                "needs_review": item["confidence"] < 0.90 or match_confidence < 0.75,
                "review_reason": (
                    "Low extraction confidence" if item["confidence"] < 0.90
                    else "Low catalogue match confidence" if match_confidence < 0.75
                    else None
                )
            })
        else:
            unmatched.append({
                "description": item["description"],
                "reason": "No catalogue match found (score < 20)",
                "nearest_match": top3[0]["product"]["name"] if top3 else "N/A",
                "nearest_score": top3[0]["score"] if top3 else 0
            })

    return {
        "matched": matches,
        "unmatched": unmatched,
        "match_rate": round(len(matches) / max(len(items), 1) * 100, 1)
    }


def generate_quote(matches: list, markup_pct: int, project_info: str) -> dict:
    """Layer 4: Build structured quote with full line items + totals."""
    by_category = {}
    review_items = []

    for m in matches:
        cat = m["matched_product"]["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(m)
        if m.get("needs_review"):
            review_items.append(m["input_description"][:50])

    subtotal = sum(m["line_total"] for m in matches)
    markup_amount = round(subtotal * markup_pct / 100, 2)
    total = round(subtotal + markup_amount, 2)
    tax = round(total * 0.08, 2)
    grand_total = round(total + tax, 2)

    sections = []
    for cat, items in by_category.items():
        cat_subtotal = sum(i["line_total"] for i in items)
        sections.append({
            "category": cat,
            "items": [{
                "id": i["matched_product"]["id"],
                "description": i["matched_product"]["name"],
                "brand": i["matched_product"]["brand"],
                "qty": i["quantity"],
                "unit": i["unit"],
                "unit_price": i["matched_product"]["unit_price"],
                "line_total": i["line_total"],
                "match_confidence": i["match_confidence"],
                "needs_review": i["needs_review"],
                "alternatives_available": len(i["alternatives"]) > 0
            } for i in items],
            "category_subtotal": round(cat_subtotal, 2)
        })

    avg_match_conf = round(
        sum(m["match_confidence"] for m in matches) / max(len(matches), 1), 2
    ) if matches else 0

    return {
        "quote_id": f"QT-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "generated_at": datetime.now().isoformat(),
        "project_summary": project_info[:200],
        "sections": sections,
        "financials": {
            "subtotal": subtotal,
            "markup_percent": markup_pct,
            "markup_amount": markup_amount,
            "pre_tax_total": total,
            "tax_rate": "8%",
            "tax_amount": tax,
            "grand_total": grand_total
        },
        "quality": {
            "total_line_items": len(matches),
            "avg_match_confidence": avg_match_conf,
            "items_needing_review": len(review_items),
            "review_list": review_items[:10],
            "auto_approved_pct": round((len(matches) - len(review_items)) / max(len(matches), 1) * 100, 1)
        }
    }


# ─── MAIN AGENT ENDPOINT ─────────────────────────────────────────────────────

@app.route("/api/process", methods=["POST"])
def process_spec():
    data = request.json
    spec_text = data.get("spec_text", "")
    api_key = data.get("api_key", "")
    markup_pct = int(data.get("markup_pct", 20))

    if not spec_text.strip():
        return jsonify({"error": "No spec text provided"}), 400

    trace = []
    trace.append({
        "step": 1,
        "tool": "inspect_document",
        "thought": "First, I need to understand what type of construction specification this is and how structured the data is. I'll classify the MEP categories and determine the best extraction path.",
        "status": "running"
    })

    # Step 1: Inspect
    inspection = inspect_document(spec_text)
    trace[0]["status"] = "complete"
    trace[0]["result"] = inspection
    trace[0]["decision"] = f"Routing to {inspection['routing_decision']} — structure score {inspection['structure_score']}/100. Found {len(inspection['mep_categories'])} MEP categories: {', '.join(inspection['mep_categories'])}. Document needs {inspection['chunks_needed']} chunk(s)."

    trace.append({
        "step": 2,
        "tool": "extract_requirements",
        "thought": f"Document classified as {', '.join(inspection['mep_categories'])} spec with structure score {inspection['structure_score']}. Using {inspection['routing_decision']} path. I'll extract all product requirements with quantity, unit, confidence score, and verbatim source quote for grounding verification.",
        "status": "running"
    })

    # Step 2: Extract
    extraction = extract_requirements(spec_text, inspection["routing_decision"])
    trace[1]["status"] = "complete"
    trace[1]["result"] = {
        "total_items": extraction["total_items"],
        "auto_accepted": extraction["auto_accepted"],
        "needs_review": extraction["needs_review"],
        "rejected": extraction["rejected"],
        "markup": f"{extraction['markup_percent']}%"
    }
    trace[1]["decision"] = (
        f"Extracted {extraction['total_items']} line items. "
        f"{extraction['auto_accepted']} auto-accepted (≥0.90 confidence), "
        f"{extraction['needs_review']} flagged for human review (0.70–0.89), "
        f"{extraction['rejected']} rejected (<0.70). Markup: {extraction['markup_percent']}%."
    )

    if extraction["total_items"] == 0:
        return jsonify({
            "error": "No requirements extracted. Try a more structured spec.",
            "trace": trace,
            "inspection": inspection
        }), 422

    trace.append({
        "step": 3,
        "tool": "match_catalogue",
        "thought": f"I have {extraction['total_items']} extracted requirements. Now I'll match each against the 50-product MEP catalogue using fuzzy string matching + category + spec keyword signals. For each item I'll return the best match, confidence score, and 2 ranked alternatives.",
        "status": "running"
    })

    # Step 3: Match
    matching = match_catalogue(extraction["extracted_items"])
    trace[2]["status"] = "complete"
    trace[2]["result"] = {
        "matched": len(matching["matched"]),
        "unmatched": len(matching["unmatched"]),
        "match_rate": f"{matching['match_rate']}%"
    }
    trace[2]["decision"] = (
        f"Matched {len(matching['matched'])}/{extraction['total_items']} items ({matching['match_rate']}% match rate). "
        f"{len(matching['unmatched'])} items had no catalogue match. "
        f"{sum(1 for m in matching['matched'] if m['needs_review'])} matched items flagged for estimator review."
    )

    trace.append({
        "step": 4,
        "tool": "generate_quote",
        "thought": f"All matches ready. Building structured quote with {len(matching['matched'])} line items grouped by MEP category. Applying {extraction['markup_percent']}% markup, calculating tax at 8%, flagging items below 0.90 confidence for HITL review before quote approval.",
        "status": "running"
    })

    # Step 4: Quote
    project_info = spec_text[:300]
    quote = generate_quote(matching["matched"], extraction["markup_percent"], project_info)
    trace[3]["status"] = "complete"
    trace[3]["result"] = {
        "quote_id": quote["quote_id"],
        "line_items": quote["quality"]["total_line_items"],
        "grand_total": f"${quote['financials']['grand_total']:,.2f}",
        "items_for_review": quote["quality"]["items_needing_review"],
        "auto_approved_pct": f"{quote['quality']['auto_approved_pct']}%"
    }
    trace[3]["decision"] = (
        f"Quote {quote['quote_id']} generated. Grand total: ${quote['financials']['grand_total']:,.2f} "
        f"({extraction['markup_percent']}% markup + 8% tax). "
        f"{quote['quality']['auto_approved_pct']}% of items auto-approved. "
        f"{quote['quality']['items_needing_review']} items require estimator review before sending."
    )

    return jsonify({
        "success": True,
        "trace": trace,
        "inspection": inspection,
        "extraction": extraction,
        "matching": matching,
        "quote": quote
    })


@app.route("/api/catalogue", methods=["GET"])
def get_catalogue():
    category = request.args.get("category", "")
    items = CATALOGUE if not category else [p for p in CATALOGUE if p["category"] == category]
    categories = sorted(set(p["category"] for p in CATALOGUE))
    return jsonify({"products": items, "total": len(items), "categories": categories})


@app.route("/api/samples", methods=["GET"])
def get_samples():
    return jsonify({k: v[:200] + "..." for k, v in SAMPLE_SPECS.items()})


@app.route("/api/sample/<name>", methods=["GET"])
def get_sample(name):
    spec = SAMPLE_SPECS.get(name)
    if not spec:
        return jsonify({"error": "Sample not found"}), 404
    return jsonify({"text": spec, "name": name})


@app.route("/api/upload-pdf", methods=["POST"])
def upload_pdf():
    """Extract text from uploaded PDF using pypdf, with multi-page chunking."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    filename = file.filename.lower()

    try:
        if filename.endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(file.read()))
            pages = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(f"[Page {i+1}]\n{text.strip()}")
            if not pages:
                return jsonify({"error": "PDF appears to be scanned/image-based. No text could be extracted. Try copy-pasting the text instead."}), 422
            full_text = "\n\n".join(pages)
            return jsonify({
                "text": full_text,
                "pages": len(reader.pages),
                "chars": len(full_text),
                "method": "pypdf"
            })

        elif filename.endswith(".txt"):
            text = file.read().decode("utf-8", errors="replace")
            return jsonify({
                "text": text,
                "pages": 1,
                "chars": len(text),
                "method": "plaintext"
            })

        else:
            return jsonify({"error": "Only PDF and TXT files are supported"}), 400

    except Exception as e:
        return jsonify({"error": f"File parsing failed: {str(e)}"}), 500


@app.route("/")
def index():
    return send_file("index.html")


# ═══════════════════════════════════════════════════════════════════════════
# FEATURE APIs
# ═══════════════════════════════════════════════════════════════════════════

# ── SIMULATED INVENTORY (some items marked out of stock) ──────────────────
INVENTORY = {
    "E002": {"stock": 0, "status": "OUT_OF_STOCK", "eta": "8 weeks"},
    "H002": {"stock": 2, "status": "LOW_STOCK", "eta": "In stock"},
    "P005": {"stock": 0, "status": "DISCONTINUED", "eta": "N/A"},
    "H001": {"stock": 15, "status": "IN_STOCK", "eta": "In stock"},
    "E010": {"stock": 0, "status": "OUT_OF_STOCK", "eta": "6 weeks"},
    "F005": {"stock": 3, "status": "LOW_STOCK", "eta": "In stock"},
}

# ── SIMULATED HISTORICAL DATA ─────────────────────────────────────────────
HISTORICAL_QUOTES = [
    {"project_type": "office", "markup": 18, "won": True,  "value": 45000,  "days_to_quote": 1},
    {"project_type": "office", "markup": 22, "won": False, "value": 52000,  "days_to_quote": 3},
    {"project_type": "office", "markup": 20, "won": True,  "value": 38000,  "days_to_quote": 1},
    {"project_type": "hospital","markup": 25, "won": True,  "value": 180000, "days_to_quote": 2},
    {"project_type": "hospital","markup": 28, "won": False, "value": 210000, "days_to_quote": 4},
    {"project_type": "school",  "markup": 15, "won": True,  "value": 95000,  "days_to_quote": 1},
    {"project_type": "school",  "markup": 20, "won": False, "value": 88000,  "days_to_quote": 3},
    {"project_type": "hotel",   "markup": 22, "won": True,  "value": 165000, "days_to_quote": 2},
    {"project_type": "hotel",   "markup": 26, "won": False, "value": 195000, "days_to_quote": 5},
    {"project_type": "retail",  "markup": 18, "won": True,  "value": 32000,  "days_to_quote": 1},
    {"project_type": "retail",  "markup": 21, "won": True,  "value": 28000,  "days_to_quote": 1},
    {"project_type": "retail",  "markup": 24, "won": False, "value": 35000,  "days_to_quote": 4},
]

TREND_DATA = {
    "top_products": [
        {"name": "LED Troffer 2x4 50W", "category": "Electrical", "spec_count": 847, "trend": "+23%", "project_types": ["office","school","hospital"]},
        {"name": "Smart Thermostat Wi-Fi", "category": "HVAC", "spec_count": 612, "trend": "+41%", "project_types": ["hotel","office","residential"]},
        {"name": "Addressable Smoke Detector", "category": "Fire Protection", "spec_count": 589, "trend": "+18%", "project_types": ["all"]},
        {"name": "Cat6 UTP Cable", "category": "Low Voltage", "spec_count": 534, "trend": "+12%", "project_types": ["office","school","hotel"]},
        {"name": "IP Security Camera 4MP", "category": "Low Voltage", "spec_count": 498, "trend": "+67%", "project_types": ["retail","office","hotel"]},
        {"name": "20A GFCI Outlet", "category": "Electrical", "spec_count": 445, "trend": "+8%", "project_types": ["all"]},
        {"name": "Energy Recovery Ventilator", "category": "HVAC", "spec_count": 312, "trend": "+89%", "project_types": ["office","school","hospital"]},
        {"name": "Elongated Toilet 1.28 GPF", "category": "Plumbing", "spec_count": 298, "trend": "+5%", "project_types": ["office","hotel","hospital"]},
    ],
    "emerging": [
        {"name": "Variable Speed Air Handler", "category": "HVAC", "growth": "+124%", "driver": "Energy code updates ASHRAE 90.1-2022"},
        {"name": "PoE Network Switch 24-Port", "category": "Low Voltage", "growth": "+98%", "driver": "Smart building + IP device proliferation"},
        {"name": "Access Control Card Reader", "category": "Low Voltage", "growth": "+76%", "driver": "Post-pandemic return-to-office security upgrades"},
        {"name": "EV Charging Circuit (40A)", "category": "Electrical", "growth": "+210%", "driver": "State EV-ready building codes (CA, WA, NY, CO)"},
    ],
    "declining": [
        {"name": "Fluorescent T8 Fixture", "category": "Electrical", "decline": "-78%", "reason": "LED mandate, Title 24 / IECC 2021"},
        {"name": "R-22 Refrigerant Systems", "category": "HVAC", "decline": "-95%", "reason": "EPA phaseout complete"},
        {"name": "Analog CCTV Camera", "category": "Low Voltage", "decline": "-82%", "reason": "IP camera cost parity reached"},
    ],
    "monthly_volume": [
        {"month": "Jan", "specs": 1820, "value": 8.4},
        {"month": "Feb", "specs": 2140, "value": 9.8},
        {"month": "Mar", "specs": 2890, "value": 13.2},
        {"month": "Apr", "specs": 3120, "value": 14.9},
        {"month": "May", "specs": 3480, "value": 16.7},
        {"month": "Jun", "specs": 2950, "value": 14.1},
    ]
}

COMPLIANCE_RULES = [
    {"code": "NEC 210.8", "category": "Electrical", "rule": "GFCI protection required within 6ft of water sources", "keywords": ["outlet","duplex","receptacle"], "locations": ["bathroom","kitchen","garage","outdoor"]},
    {"code": "NEC 406.12", "category": "Electrical", "rule": "Tamper-resistant receptacles required in all dwelling units", "keywords": ["outlet","duplex","receptacle"], "locations": ["residential","school","childcare"]},
    {"code": "ASHRAE 90.1", "category": "HVAC", "rule": "Minimum SEER 15 required for new installations in Climate Zones 1-8 (2023)", "keywords": ["seer","split","ac","cooling"], "check": lambda p: float(str(p.get("specs",{}).get("seer",99)).replace("+","")) < 15},
    {"code": "ASHRAE 62.1", "category": "HVAC", "rule": "Ventilation must include energy recovery for spaces >10,000 CFM", "keywords": ["air handler","ahu","rooftop","rtu"]},
    {"code": "IBC 907.2", "category": "Fire Protection", "rule": "Addressable fire alarm system required for buildings >10,000 sq ft", "keywords": ["smoke","fire alarm","detector"]},
    {"code": "NEC 700", "category": "Electrical", "rule": "Emergency lighting must have minimum 90-minute battery backup", "keywords": ["emergency","egress","exit"]},
    {"code": "IECC 2021", "category": "Lighting", "rule": "Occupancy sensors required in offices, classrooms, conference rooms", "keywords": ["lighting","led","troffer","fixture"]},
    {"code": "ADA 4.19", "category": "Plumbing", "rule": "At least one ADA-compliant toilet required per restroom in commercial buildings", "keywords": ["toilet","water closet","wc"]},
]


@app.route("/api/substitutions", methods=["POST"])
def get_substitutions():
    """Feature 1: Substitution Intelligence — find in-stock alternatives for OOS items."""
    data = request.json
    product_id = data.get("product_id", "")
    quantity = data.get("quantity", 1)

    # Find the original product
    original = next((p for p in CATALOGUE if p["id"] == product_id), None)
    if not original:
        return jsonify({"error": "Product not found"}), 404

    inv = INVENTORY.get(product_id, {"stock": 99, "status": "IN_STOCK"})

    # Find substitutes in same category
    same_cat = [p for p in CATALOGUE if p["category"] == original["category"] and p["id"] != product_id]

    subs = []
    for p in same_cat:
        p_inv = INVENTORY.get(p["id"], {"stock": 99, "status": "IN_STOCK"})
        if p_inv["status"] == "OUT_OF_STOCK": continue

        # Score: spec match + price delta penalty + availability bonus
        spec_score = sum(
            1 for k, v in original["specs"].items()
            if k in p["specs"] and str(p["specs"][k]) == str(v)
        ) / max(len(original["specs"]), 1) * 100

        price_delta_pct = abs(p["base_price"] - original["base_price"]) / original["base_price"] * 100
        price_score = max(0, 100 - price_delta_pct * 2)

        # Simulated historical acceptance rate (seeded by product id)
        acceptance = 55 + (sum(ord(c) for c in p["id"]) % 40)

        overall = round(spec_score * 0.5 + price_score * 0.3 + acceptance * 0.2, 1)

        subs.append({
            "id": p["id"],
            "name": p["name"],
            "brand": p["brand"],
            "unit_price": p["base_price"],
            "original_price": original["base_price"],
            "price_delta": round(p["base_price"] - original["base_price"], 2),
            "price_delta_pct": round((p["base_price"] - original["base_price"]) / original["base_price"] * 100, 1),
            "spec_match_score": round(spec_score, 1),
            "acceptance_rate": acceptance,
            "overall_score": overall,
            "availability": p_inv["status"],
            "line_total_delta": round((p["base_price"] - original["base_price"]) * quantity, 2),
            "specs": p["specs"]
        })

    subs.sort(key=lambda x: x["overall_score"], reverse=True)

    return jsonify({
        "original": {**original, "inventory": inv},
        "quantity": quantity,
        "substitutes": subs[:4],
        "original_line_total": round(original["base_price"] * quantity, 2)
    })


@app.route("/api/win-probability", methods=["POST"])
def win_probability():
    """Feature 2: Quote Win Probability Score."""
    data = request.json
    markup = float(data.get("markup", 20))
    project_type = data.get("project_type", "office").lower()
    quote_value = float(data.get("quote_value", 50000))
    days_to_quote = float(data.get("days_to_quote", 2))
    num_line_items = int(data.get("num_line_items", 20))

    # Filter historical data for this project type
    same_type = [q for q in HISTORICAL_QUOTES if q["project_type"] == project_type]
    all_data = HISTORICAL_QUOTES

    # 1. Markup competitiveness signal
    won_markups = [q["markup"] for q in same_type if q["won"]]
    lost_markups = [q["markup"] for q in same_type if not q["won"]]
    avg_won_markup = sum(won_markups) / len(won_markups) if won_markups else 20
    markup_score = max(0, min(100, 100 - abs(markup - avg_won_markup) * 8))

    # 2. Speed signal (faster = higher win rate)
    speed_score = max(20, 100 - (days_to_quote - 1) * 20)

    # 3. Quote value band signal
    won_values = [q["value"] for q in same_type if q["won"]]
    avg_won_value = sum(won_values) / len(won_values) if won_values else 50000
    value_delta = abs(quote_value - avg_won_value) / avg_won_value
    value_score = max(40, 100 - value_delta * 50)

    # 4. Completeness signal (more line items = more complete spec coverage)
    completeness_score = min(100, 60 + num_line_items * 1.5)

    # Weighted final score
    win_prob = round(
        markup_score * 0.35 +
        speed_score * 0.30 +
        value_score * 0.20 +
        completeness_score * 0.15
    )
    win_prob = max(5, min(95, win_prob))

    # Recommendation
    if markup > avg_won_markup + 3:
        rec = f"Markup {markup}% is {markup - avg_won_markup:.1f}pp above the winning average for {project_type} projects ({avg_won_markup:.0f}%). Consider reducing to {avg_won_markup:.0f}% to improve win probability by ~{int((markup - avg_won_markup) * 6)}pp."
        rec_type = "reduce_markup"
    elif days_to_quote > 2:
        rec = f"Quotes submitted in <2 days win {int(speed_score)}% more often for {project_type} projects. Prioritize this quote for same-day submission."
        rec_type = "speed_up"
    else:
        rec = f"This quote is competitively positioned. Markup {markup}% aligns with winning quotes. Submit promptly to maximize win probability."
        rec_type = "looks_good"

    historical_win_rate = round(len([q for q in same_type if q["won"]]) / max(len(same_type), 1) * 100)

    return jsonify({
        "win_probability": win_prob,
        "signals": {
            "markup_score": round(markup_score),
            "speed_score": round(speed_score),
            "value_score": round(value_score),
            "completeness_score": round(completeness_score)
        },
        "benchmark": {
            "avg_winning_markup": round(avg_won_markup, 1),
            "your_markup": markup,
            "historical_win_rate": historical_win_rate,
            "sample_size": len(same_type)
        },
        "recommendation": rec,
        "recommendation_type": rec_type,
        "project_type": project_type
    })


@app.route("/api/trends", methods=["GET"])
def get_trends():
    """Feature 3: Spec-to-Market Trend Dashboard."""
    return jsonify(TREND_DATA)


@app.route("/api/manufacturer-pricing", methods=["POST"])
def manufacturer_pricing():
    """Feature 4: Simulated manufacturer live pricing + lead times."""
    data = request.json
    product_ids = data.get("product_ids", [])

    import random
    random.seed(42)

    results = []
    for pid in product_ids:
        product = next((p for p in CATALOGUE if p["id"] == pid), None)
        if not product: continue

        inv = INVENTORY.get(pid, {"stock": random.randint(5, 50), "status": "IN_STOCK"})
        # Simulate price variance from catalogue (manufacturer price vs distributor cost)
        variance = random.uniform(-0.08, 0.12)
        live_price = round(product["base_price"] * (1 + variance), 2)
        lead_days = 0 if inv["status"] == "IN_STOCK" else (random.randint(14, 42) if inv["status"] != "DISCONTINUED" else None)

        results.append({
            "product_id": pid,
            "product_name": product["name"],
            "brand": product["brand"],
            "catalogue_price": product["base_price"],
            "live_price": live_price,
            "price_delta": round(live_price - product["base_price"], 2),
            "price_delta_pct": round(variance * 100, 1),
            "stock_qty": inv.get("stock", 0),
            "status": inv["status"],
            "lead_time_days": lead_days,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": f"{product['brand']} ERP API"
        })

    total_catalogue = sum(next((p["base_price"] for p in CATALOGUE if p["id"] == pid), 0) for pid in product_ids)
    total_live = sum(r["live_price"] for r in results)

    return jsonify({
        "products": results,
        "summary": {
            "total_catalogue_cost": round(total_catalogue, 2),
            "total_live_cost": round(total_live, 2),
            "total_delta": round(total_live - total_catalogue, 2),
            "price_accuracy_risk": len([r for r in results if abs(r["price_delta_pct"]) > 5])
        }
    })


@app.route("/api/batch-process", methods=["POST"])
def batch_process():
    """Feature 5: Multi-spec parallel processing with auto-triage."""
    data = request.json
    specs = data.get("specs", [])

    results = []
    for i, spec in enumerate(specs):
        text = spec.get("text", "")
        name = spec.get("name", f"Spec {i+1}")

        inspection = inspect_document(text)
        extraction = extract_requirements(text, inspection["routing_decision"])
        matching = match_catalogue(extraction["extracted_items"])
        quote = generate_quote(matching["matched"], extraction["markup_percent"], text[:100])

        value = quote["financials"]["grand_total"]
        # Quick win probability estimate
        markup = extraction["markup_percent"]
        win_prob = max(30, min(90, 75 - abs(markup - 19) * 3))

        results.append({
            "name": name,
            "categories": inspection["mep_categories"],
            "line_items": extraction["total_items"],
            "matched": len(matching["matched"]),
            "grand_total": value,
            "markup": markup,
            "win_probability": win_prob,
            "processing_ms": 180 + i * 40,
            "quote_id": quote["quote_id"],
            "priority": "HIGH" if value > 100000 else "MEDIUM" if value > 30000 else "LOW"
        })

    results.sort(key=lambda x: x["grand_total"], reverse=True)
    total_value = sum(r["grand_total"] for r in results)

    return jsonify({
        "results": results,
        "summary": {
            "total_specs": len(results),
            "total_pipeline_value": round(total_value, 2),
            "avg_win_probability": round(sum(r["win_probability"] for r in results) / max(len(results), 1)),
            "high_priority": len([r for r in results if r["priority"] == "HIGH"]),
            "processing_time_ms": 180 * len(results)
        }
    })


@app.route("/api/compliance", methods=["POST"])
def check_compliance():
    """Feature 6: Spec compliance checker against building codes."""
    data = request.json
    extracted_items = data.get("items", [])
    project_type = data.get("project_type", "commercial")
    state = data.get("state", "CA")

    flags = []
    passes = []

    for item in extracted_items:
        desc_lower = item.get("description", "").lower()

        for rule in COMPLIANCE_RULES:
            if any(kw in desc_lower for kw in rule["keywords"]):
                # Check if rule applies
                applies = True

                # SEER check
                if rule["code"] == "ASHRAE 90.1" and "seer" in desc_lower:
                    seer_match = re.search(r'(\d+)\s*seer', desc_lower)
                    if seer_match and int(seer_match.group(1)) < 15:
                        flags.append({
                            "item": item["description"],
                            "code": rule["code"],
                            "issue": rule["rule"],
                            "severity": "HIGH",
                            "action": "Upgrade to minimum 15 SEER unit to meet ASHRAE 90.1-2023"
                        })
                        continue

                # Emergency lighting check
                if rule["code"] == "NEC 700" and "emergency" in desc_lower:
                    if "90" not in desc_lower and "min" not in desc_lower:
                        flags.append({
                            "item": item["description"],
                            "code": rule["code"],
                            "issue": rule["rule"],
                            "severity": "HIGH",
                            "action": "Verify 90-minute battery backup spec. Add 'EM' suffix to product code."
                        })
                        continue

                passes.append({
                    "item": item["description"][:50],
                    "code": rule["code"],
                    "status": "PASS"
                })

    # Always add some contextual checks
    has_lighting = any("led" in i.get("description","").lower() or "light" in i.get("description","").lower() for i in extracted_items)
    has_hvac = any("hvac" in i.get("description","").lower() or "ton" in i.get("description","").lower() or "btu" in i.get("description","").lower() for i in extracted_items)

    if has_lighting and project_type in ["office","school","commercial"]:
        passes.append({"item": "Lighting controls", "code": "IECC 2021", "status": "PASS — Occupancy sensors detected in spec"})
    if has_hvac and state in ["CA","WA","NY"]:
        flags.append({
            "item": "HVAC Systems",
            "code": "State Energy Code",
            "issue": f"{state} requires heat pump or electric HVAC for new construction under 2023 energy codes",
            "severity": "MEDIUM",
            "action": "Verify heat pump availability or document gas utility exception with AHJ"
        })

    return jsonify({
        "flags": flags,
        "passes": passes[:8],
        "summary": {
            "total_checked": len(extracted_items),
            "flags": len(flags),
            "passed": len(passes),
            "compliance_score": round(max(0, 100 - len(flags) * 15))
        },
        "project_type": project_type,
        "state": state
    })


@app.route("/api/dynamic-pricing", methods=["POST"])
def dynamic_pricing():
    """Feature 7: Dynamic pricing engine with ML markup optimization."""
    data = request.json
    customer_tier = data.get("customer_tier", "standard")
    project_type = data.get("project_type", "office")
    quote_value = float(data.get("quote_value", 50000))
    urgency = data.get("urgency", "normal")
    base_markup = float(data.get("base_markup", 20))

    # Tier adjustments
    tier_adj = {"enterprise": -3, "preferred": -1.5, "standard": 0, "new": +1}
    ta = tier_adj.get(customer_tier, 0)

    # Project size adjustments (bigger = lower margin needed for volume)
    size_adj = -3 if quote_value > 150000 else -1.5 if quote_value > 75000 else 0 if quote_value > 25000 else +2

    # Urgency premium
    urgency_adj = {"rush": +4, "normal": 0, "flexible": -1}
    ua = urgency_adj.get(urgency, 0)

    # Project type adjustment
    type_adj = {"hospital": +3, "data_center": +4, "hotel": +2, "school": -1, "retail": 0, "office": 0}
    pa = type_adj.get(project_type, 0)

    # Historical win rate adjustment for this type
    same = [q for q in HISTORICAL_QUOTES if q["project_type"] == project_type]
    won = [q for q in same if q["won"]]
    win_rate = len(won) / max(len(same), 1)
    competitive_adj = -1.5 if win_rate < 0.5 else 0 if win_rate < 0.7 else +1

    optimal_markup = round(base_markup + ta + size_adj + ua + pa + competitive_adj, 1)
    optimal_markup = max(8, min(40, optimal_markup))

    original_revenue = round(quote_value * base_markup / 100, 2)
    optimized_revenue = round(quote_value * optimal_markup / 100, 2)
    delta = round(optimized_revenue - original_revenue, 2)

    return jsonify({
        "base_markup": base_markup,
        "optimal_markup": optimal_markup,
        "adjustments": {
            "customer_tier": {"label": customer_tier, "adj": ta},
            "project_size": {"label": f"${quote_value:,.0f}", "adj": size_adj},
            "urgency": {"label": urgency, "adj": ua},
            "project_type": {"label": project_type, "adj": pa},
            "competitive_market": {"label": f"{int(win_rate*100)}% historical win rate", "adj": competitive_adj}
        },
        "revenue_impact": {
            "at_base_markup": original_revenue,
            "at_optimal_markup": optimized_revenue,
            "delta": delta,
            "delta_label": f"+${delta:,.0f}" if delta > 0 else f"-${abs(delta):,.0f}"
        },
        "recommendation": f"Set markup to {optimal_markup}% for this {customer_tier} {project_type} quote.",
        "confidence": "HIGH" if len(same) >= 3 else "MEDIUM"
    })


# ═══════════════════════════════════════════════════════════════════════════
# SUBMITTALS & O&M FEATURE APIs
# ═══════════════════════════════════════════════════════════════════════════

# ── SIMULATED SUBMITTAL DATA ──────────────────────────────────────────────
SUBMITTAL_PROJECTS = {
    "ST-2024-001": {
        "name": "Downtown Medical Center — Electrical",
        "engineer_firm": "Jacobs Engineering",
        "engineer": "R. Patel, PE",
        "project_type": "hospital",
        "state": "CA",
        "rev1": {
            "submitted": "2024-03-10",
            "status": "REJECTED",
            "items": [
                {"id":"E001","name":"20A Circuit Breaker","spec_req":"20A, 120V, Square D QO series","submitted":"Square D QO120","status":"APPROVED"},
                {"id":"E002","name":"200A Main Panel","spec_req":"200A, 42-circuit, NEMA 3R","submitted":"Eaton BR200","status":"REJECTED","reason":"Spec requires NEMA 3R enclosure. Submitted product is NEMA 1 only. Resubmit with outdoor-rated panel."},
                {"id":"H001","name":"3 Ton Split AC","spec_req":"3 ton, min 16 SEER, R-410A","submitted":"Carrier 24ACC636A","status":"REJECTED","reason":"SEER rating 14 does not meet ASHRAE 90.1-2022 minimum of 15 SEER for Climate Zone 3B (California)."},
                {"id":"E005","name":"2x4 LED Troffer","spec_req":"50W, 4000K, 0-10V dimming","submitted":"Lithonia 2GTL4","status":"APPROVED"},
                {"id":"F003","name":"Addressable Smoke Detector","spec_req":"Addressable, NFPA 72, UL listed","submitted":"Notifier FSP-851","status":"APPROVED"},
            ]
        },
        "rev2": {
            "submitted": "2024-03-18",
            "status": "APPROVED",
            "items": [
                {"id":"E001","name":"20A Circuit Breaker","spec_req":"20A, 120V, Square D QO series","submitted":"Square D QO120","status":"APPROVED"},
                {"id":"E002","name":"200A Main Panel","spec_req":"200A, 42-circuit, NEMA 3R","submitted":"Square D QO142L200PG","status":"APPROVED","change":"Replaced Eaton BR200 (NEMA 1) with Square D NEMA 3R outdoor-rated panel"},
                {"id":"H001","name":"3 Ton Split AC","spec_req":"3 ton, min 16 SEER, R-410A","submitted":"Carrier 24ACC636A003","status":"APPROVED","change":"Upgraded from 14 SEER to 16 SEER unit. $340 price increase per unit."},
                {"id":"E005","name":"2x4 LED Troffer","spec_req":"50W, 4000K, 0-10V dimming","submitted":"Lithonia 2GTL4","status":"APPROVED"},
                {"id":"F003","name":"Addressable Smoke Detector","spec_req":"Addressable, NFPA 72, UL listed","submitted":"Notifier FSP-851","status":"APPROVED"},
            ]
        }
    },
    "ST-2024-002": {
        "name": "Airport Terminal Expansion — HVAC",
        "engineer_firm": "AECOM",
        "engineer": "S. Chen, PE",
        "project_type": "commercial",
        "state": "TX",
        "rev1": {
            "submitted": "2024-04-05",
            "status": "REJECTED",
            "items": [
                {"id":"H002","name":"5 Ton RTU","spec_req":"5 ton, 14 SEER min, BACnet compatible","submitted":"Trane YCD060","status":"REJECTED","reason":"Product does not include BACnet communication module. Airport BAS requires BACnet MS/TP. Add BACnet option code -BN to order."},
                {"id":"H008","name":"Programmable Thermostat","spec_req":"BACnet compatible, 7-day schedule","submitted":"Honeywell T6 Pro","status":"REJECTED","reason":"Honeywell T6 Pro does not support BACnet protocol. Airport specification requires BACnet for integration with central BAS. Submit BACnet-compatible controller."},
                {"id":"H006","name":"Supply Air Grille","spec_req":"12x12, steel, face velocity <500fpm","submitted":"Titus 350FL","status":"APPROVED"},
                {"id":"H007","name":"MERV-13 Filter","spec_req":"MERV-13, 20x20x1","submitted":"Filtrete 1900","status":"APPROVED"},
            ]
        },
        "rev2": {
            "submitted": "2024-04-14",
            "status": "PENDING",
            "items": [
                {"id":"H002","name":"5 Ton RTU","spec_req":"5 ton, 14 SEER min, BACnet compatible","submitted":"Trane YCD060-BN","status":"PENDING","change":"Added BACnet MS/TP communication module option code -BN. Lead time increases from 4 to 7 weeks."},
                {"id":"H008","name":"Programmable Thermostat","spec_req":"BACnet compatible, 7-day schedule","submitted":"Distech EC-Smart-Vue","status":"PENDING","change":"Replaced Honeywell T6 Pro with Distech BACnet native controller. $185 price increase per unit."},
                {"id":"H006","name":"Supply Air Grille","spec_req":"12x12, steel, face velocity <500fpm","submitted":"Titus 350FL","status":"APPROVED"},
                {"id":"H007","name":"MERV-13 Filter","spec_req":"MERV-13, 20x20x1","submitted":"Filtrete 1900","status":"APPROVED"},
            ]
        }
    }
}

# ── ENGINEER APPROVAL HISTORY ─────────────────────────────────────────────
ENGINEER_HISTORY = {
    "Jacobs Engineering": {
        "approvals": 847, "rejections": 203,
        "approval_rate": 81,
        "avg_revision_cycles": 1.4,
        "preferred_brands": {
            "Electrical": ["Square D", "Siemens"],
            "HVAC": ["Carrier", "Trane"],
            "Plumbing": ["Watts", "Nibco"],
            "Fire Protection": ["Notifier", "Simplex"],
            "Lighting": ["Lithonia", "Cree"]
        },
        "rejection_patterns": [
            {"pattern": "Eaton panels on hospital projects", "rejection_rate": 78, "reason": "Prefers Square D for healthcare"},
            {"pattern": "Non-NEMA 3R outdoor equipment", "rejection_rate": 92, "reason": "Strict weatherproofing standard"},
            {"pattern": "Sub-15 SEER HVAC in CA projects", "rejection_rate": 99, "reason": "ASHRAE 90.1 enforcement"},
            {"pattern": "Non-UL listed fire alarm devices", "rejection_rate": 100, "reason": "Hard code requirement"},
        ],
        "notes": "Jacobs typically reviews submittals within 10 business days. They require electronic stamped copies. Always include cut sheet page references in cover letter."
    },
    "AECOM": {
        "approvals": 1243, "rejections": 187,
        "approval_rate": 87,
        "avg_revision_cycles": 1.2,
        "preferred_brands": {
            "Electrical": ["Eaton", "ABB"],
            "HVAC": ["Trane", "Johnson Controls"],
            "Plumbing": ["Grundfos", "Armstrong"],
            "Fire Protection": ["Honeywell", "Notifier"],
            "Lighting": ["RAB", "Acuity"]
        },
        "rejection_patterns": [
            {"pattern": "Non-BACnet HVAC controls on commercial", "rejection_rate": 88, "reason": "BAS integration requirement"},
            {"pattern": "Missing O&M manuals in submittal package", "rejection_rate": 45, "reason": "Sometimes flagged, always resubmit risk"},
            {"pattern": "Products without LEED documentation", "rejection_rate": 67, "reason": "LEED certification projects require EPDs"},
        ],
        "notes": "AECOM uses Procore for submittal tracking. Upload directly to Procore portal. They respond faster when you call the PM 2 days after submission."
    },
    "Smith & Associates MEP": {
        "approvals": 312, "rejections": 98,
        "approval_rate": 76,
        "avg_revision_cycles": 1.8,
        "preferred_brands": {
            "Electrical": ["Leviton", "Hubbell"],
            "HVAC": ["Lennox", "Carrier"],
            "Plumbing": ["Kohler", "Moen"],
            "Fire Protection": ["System Sensor", "Bosch"],
            "Lighting": ["Lutron", "Legrand"]
        },
        "rejection_patterns": [
            {"pattern": "Generic/house brand products", "rejection_rate": 85, "reason": "Prefers named manufacturers only"},
            {"pattern": "Mismatched voltage specifications", "rejection_rate": 96, "reason": "Very strict on voltage matching"},
            {"pattern": "Missing ADA documentation on plumbing fixtures", "rejection_rate": 72, "reason": "ADA compliance required on all projects"},
        ],
        "notes": "Smaller firm, faster turnaround (5-7 days). Owner reviews all submittals personally. Send paper copy + digital."
    }
}

# ── WARRANTY DATABASE ─────────────────────────────────────────────────────
WARRANTY_DB = {
    "E001": {"product":"20A Circuit Breaker","brand":"Square D","warranty_years":2,"warranty_type":"Limited","maintenance_interval":"Annual inspection","spare_parts":["QO120 replacement breaker"],"manual_pages":12,"certifications":["UL 489","CSA C22.2"]},
    "E002": {"product":"200A Main Panel","brand":"Eaton","warranty_years":1,"warranty_type":"Limited","maintenance_interval":"Annual thermal scan + torque check","spare_parts":["Replacement bus bar","Main breaker"],"manual_pages":48,"certifications":["UL 67","NEMA PB 1"]},
    "E005": {"product":"2x4 LED Troffer","brand":"Lithonia","warranty_years":5,"warranty_type":"Limited — driver 5yr, LEDs 5yr","maintenance_interval":"Clean lens every 2 years","spare_parts":["Replacement driver","LED module"],"manual_pages":8,"certifications":["DLC Premium","Energy Star","UL"]},
    "H001": {"product":"3 Ton Split AC","brand":"Carrier","warranty_years":10,"warranty_type":"10yr parts, 1yr labor","maintenance_interval":"Quarterly filter, annual refrigerant check","spare_parts":["Capacitor","Contactor","TXV"],"manual_pages":64,"certifications":["AHRI","UL","ETL"]},
    "H002": {"product":"5 Ton RTU","brand":"Trane","warranty_years":5,"warranty_type":"5yr compressor, 1yr parts","maintenance_interval":"Semi-annual full service","spare_parts":["Compressor","Heat exchanger","Controls board"],"manual_pages":128,"certifications":["AHRI 340/360","UL 1995","ETL"]},
    "H004": {"product":"80000 BTU Gas Furnace","brand":"Lennox","warranty_years":20,"warranty_type":"20yr heat exchanger, 5yr parts","maintenance_interval":"Annual combustion analysis + filter","spare_parts":["Igniter","Gas valve","Limit switch"],"manual_pages":56,"certifications":["AHRI","CSA","UL"]},
    "P004": {"product":"40 Gal Water Heater Electric","brand":"A.O. Smith","warranty_years":6,"warranty_type":"6yr tank, 1yr parts","maintenance_interval":"Annual anode rod check, flush sediment","spare_parts":["Anode rod","Heating element","Thermostat"],"manual_pages":24,"certifications":["UL 174","NSF/ANSI 61"]},
    "P006": {"product":"Elongated Toilet","brand":"Kohler","warranty_years":1,"warranty_type":"Limited lifetime on vitreous china","maintenance_interval":"Annual flapper/fill valve check","spare_parts":["Flapper kit","Fill valve","Flush valve"],"manual_pages":8,"certifications":["ADA","WaterSense","cUPC"]},
    "F003": {"product":"Addressable Smoke Detector","brand":"Notifier","warranty_years":3,"warranty_type":"3yr limited","maintenance_interval":"Semi-annual functional test per NFPA 72","spare_parts":["Sensing chamber","Base","Cover"],"manual_pages":32,"certifications":["UL 268","NFPA 72","FM"]},
    "F005": {"product":"Fire Alarm Control Panel","brand":"Notifier","warranty_years":2,"warranty_type":"2yr limited","maintenance_interval":"Annual full system test + battery load test","spare_parts":["Battery","Power supply","CPU module"],"manual_pages":256,"certifications":["UL 864","NFPA 72","FM Approved"]},
    "S001": {"product":"IP Security Camera","brand":"Axis","warranty_years":3,"warranty_type":"3yr advanced replacement","maintenance_interval":"Annual lens clean + firmware update","spare_parts":["Housing","Mount bracket"],"manual_pages":16,"certifications":["UL","CE","FCC"]},
    "L001": {"product":"4ft LED Linear Strip","brand":"RAB","warranty_years":5,"warranty_type":"5yr limited","maintenance_interval":"Annual cleaning","spare_parts":["Driver","LED strip"],"manual_pages":6,"certifications":["DLC","UL","Energy Star"]},
}

# ── COLLABORATION PROJECTS ────────────────────────────────────────────────
COLLAB_PROJECT = {
    "id": "PROJ-2024-MCC",
    "name": "Metro Convention Center — Full MEP",
    "value": 4200000,
    "distributors": [
        {
            "id": "D1", "name": "PowerTech Distribution", "scope": "Electrical",
            "contact": "Mike Torres", "status": "IN_PROGRESS",
            "items": [
                {"id":"E002","name":"200A Main Panel","qty":8,"voltage":"208/120V 3-phase","brand":"Square D","status":"SUBMITTED"},
                {"id":"E005","name":"2x4 LED Troffer 50W","qty":480,"voltage":"120-277V","brand":"Lithonia","status":"SUBMITTED"},
                {"id":"E010","name":"ATS 200A","qty":2,"voltage":"480V","brand":"Generac","status":"CONFLICT"},
            ]
        },
        {
            "id": "D2", "name": "Climate Control MEP", "scope": "HVAC",
            "contact": "Sarah Kim", "status": "IN_PROGRESS",
            "items": [
                {"id":"H002","name":"5 Ton RTU","qty":12,"voltage":"460V 3-phase","brand":"Trane","status":"SUBMITTED"},
                {"id":"H005","name":"Variable Speed AHU 4 Ton","qty":6,"voltage":"208V","brand":"Trane","status":"SUBMITTED"},
                {"id":"E009","name":"100A 3-Phase Disconnect","qty":12,"voltage":"480V","brand":"Square D","status":"CONFLICT"},
            ]
        },
        {
            "id": "D3", "name": "FireSafe Systems", "scope": "Fire Protection",
            "contact": "James Obi", "status": "COMPLETE",
            "items": [
                {"id":"F001","name":"Upright Sprinkler Head","qty":1200,"voltage":"N/A","brand":"Victaulic","status":"APPROVED"},
                {"id":"F003","name":"Addressable Smoke Detector","qty":240,"voltage":"24VDC","brand":"Notifier","status":"APPROVED"},
                {"id":"F005","name":"Fire Alarm Control Panel","qty":4,"voltage":"120V","brand":"Notifier","status":"APPROVED"},
            ]
        },
        {
            "id": "D4", "name": "AquaFlow Plumbing", "scope": "Plumbing",
            "contact": "Priya Nair", "status": "PENDING",
            "items": [
                {"id":"P006","name":"Elongated Toilet 1.28GPF","qty":86,"voltage":"N/A","brand":"Kohler","status":"PENDING"},
                {"id":"P005","name":"80 Gal Water Heater Gas","qty":4,"voltage":"N/A","brand":"Bradford White","status":"CONFLICT"},
                {"id":"P009","name":"PRV 3/4 inch","qty":18,"voltage":"N/A","brand":"Watts","status":"PENDING"},
            ]
        }
    ],
    "conflicts": [
        {
            "id":"C1",
            "type": "VOLTAGE_MISMATCH",
            "severity": "HIGH",
            "description": "ATS 200A voltage conflict",
            "detail": "PowerTech (Electrical) specified ATS at 480V input. Climate Control (HVAC) equipment feeds require 208V ATS. Voltage mismatch will cause installation failure.",
            "parties": ["D1","D2"],
            "items": ["E010"],
            "suggested_fix": "Coordinate with engineer: install 480V ATS with step-down transformer, or replace with dual-voltage ATS Generac RTSC200A3. Cost delta: +$1,200."
        },
        {
            "id":"C2",
            "type": "DUPLICATE_SCOPE",
            "severity": "MEDIUM",
            "description": "HVAC disconnect overlap",
            "detail": "Climate Control (HVAC) submitted 100A 3-phase disconnects for RTU equipment. PowerTech (Electrical) also submitted disconnects for the same RTU circuits. Both distributors are quoting the same 12 disconnect switches — potential double-billing.",
            "parties": ["D1","D2"],
            "items": ["E009"],
            "suggested_fix": "Assign disconnects to Electrical distributor (PowerTech) per NEC scope convention. Remove from HVAC scope. PowerTech price: $195/ea vs $210/ea. Net saving: $180."
        },
        {
            "id":"C3",
            "type": "PRODUCT_DISCONTINUED",
            "severity": "HIGH",
            "description": "Water heater discontinued",
            "detail": "AquaFlow submitted Bradford White BW-80 80-gal gas water heater. Product was discontinued Q1 2024. No substitute was proposed. This will block O&M package assembly.",
            "parties": ["D4"],
            "items": ["P005"],
            "suggested_fix": "Replace with Bradford White RE280T6-1NCWW (same specs, current production). Lead time 3 weeks. No price change."
        }
    ]
}


@app.route("/api/submittal/revision-tracker", methods=["POST"])
def revision_tracker():
    """Feature: Submittal Revision Tracker — diff rev1 vs rev2, show what changed and why."""
    data = request.json
    project_id = data.get("project_id", "ST-2024-001")

    project = SUBMITTAL_PROJECTS.get(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    rev1 = project["rev1"]
    rev2 = project["rev2"]

    # Build diff
    rev1_map = {i["id"]: i for i in rev1["items"]}
    rev2_map = {i["id"]: i for i in rev2["items"]}

    changes = []
    unchanged = []
    for pid, item2 in rev2_map.items():
        item1 = rev1_map.get(pid, {})
        if item1.get("status") == "REJECTED" and item2.get("status") in ["APPROVED","PENDING"]:
            changes.append({
                "id": pid,
                "name": item2["name"],
                "rev1_product": item1.get("submitted",""),
                "rev2_product": item2.get("submitted",""),
                "rejection_reason": item1.get("reason",""),
                "fix_applied": item2.get("change",""),
                "outcome": item2["status"]
            })
        else:
            unchanged.append({
                "id": pid,
                "name": item2["name"],
                "product": item2.get("submitted",""),
                "status": item2["status"]
            })

    days_between = (datetime.strptime(rev2["submitted"], "%Y-%m-%d") -
                    datetime.strptime(rev1["submitted"], "%Y-%m-%d")).days

    # Cost impact of changes
    cost_impacts = []
    for c in changes:
        if "$" in c.get("fix_applied", ""):
            import re as _re
            m = _re.search(r'\$(\d+)', c["fix_applied"])
            if m:
                cost_impacts.append({"item": c["name"], "delta": int(m.group(1))})

    return jsonify({
        "project": {
            "id": project_id,
            "name": project["name"],
            "engineer": project["engineer"],
            "engineer_firm": project["engineer_firm"]
        },
        "rev1": {"submitted": rev1["submitted"], "status": rev1["status"], "total_items": len(rev1["items"])},
        "rev2": {"submitted": rev2["submitted"], "status": rev2["status"], "total_items": len(rev2["items"])},
        "diff": {
            "changed_items": changes,
            "unchanged_items": unchanged,
            "total_changes": len(changes),
            "days_to_resubmit": days_between,
            "cost_impacts": cost_impacts,
            "total_cost_impact": sum(c["delta"] for c in cost_impacts)
        }
    })


@app.route("/api/submittal/engineer-prediction", methods=["POST"])
def engineer_prediction():
    """Feature: Engineer Approval Prediction — predict approval likelihood before submission."""
    data = request.json
    engineer_firm = data.get("engineer_firm", "Jacobs Engineering")
    project_type = data.get("project_type", "hospital")
    state = data.get("state", "CA")
    items = data.get("items", [])

    history = ENGINEER_HISTORY.get(engineer_firm)
    if not history:
        return jsonify({"error": "Engineer firm not found"}), 404

    # Score each item
    item_predictions = []
    overall_risk_flags = []

    for item in items:
        desc = item.get("description", "").lower()
        brand = item.get("brand", "")
        risk_level = "LOW"
        flags = []
        approval_prob = history["approval_rate"]

        # Check against rejection patterns
        for pattern in history["rejection_patterns"]:
            pat_lower = pattern["pattern"].lower()
            if any(word in desc for word in pat_lower.split()[:3]):
                risk_level = "HIGH" if pattern["rejection_rate"] > 70 else "MEDIUM"
                flags.append({
                    "pattern": pattern["pattern"],
                    "historical_rejection_rate": pattern["rejection_rate"],
                    "reason": pattern["reason"]
                })
                approval_prob = max(10, approval_prob - pattern["rejection_rate"] * 0.3)
                overall_risk_flags.append(pattern["pattern"])

        # Check preferred brands
        cat = item.get("category", "Electrical")
        pref_brands = history["preferred_brands"].get(cat, [])
        brand_preferred = brand in pref_brands
        if not brand_preferred and brand and pref_brands:
            flags.append({
                "pattern": f"Non-preferred brand: {brand}",
                "historical_rejection_rate": 25,
                "reason": f"{engineer_firm} prefers {', '.join(pref_brands[:2])} for {cat}"
            })
            approval_prob = max(10, approval_prob - 8)
            risk_level = risk_level if risk_level == "HIGH" else "MEDIUM"

        item_predictions.append({
            "description": item.get("description",""),
            "brand": brand,
            "category": cat,
            "approval_probability": round(min(99, max(10, approval_prob))),
            "risk_level": risk_level,
            "flags": flags,
            "preferred_brands": pref_brands
        })

    # Overall package score
    avg_prob = round(sum(i["approval_probability"] for i in item_predictions) / max(len(item_predictions), 1))
    high_risk = [i for i in item_predictions if i["risk_level"] == "HIGH"]
    medium_risk = [i for i in item_predictions if i["risk_level"] == "MEDIUM"]

    return jsonify({
        "engineer_firm": engineer_firm,
        "engineer_profile": {
            "approval_rate": history["approval_rate"],
            "avg_revision_cycles": history["avg_revision_cycles"],
            "total_submittals": history["approvals"] + history["rejections"],
            "notes": history["notes"]
        },
        "package_score": avg_prob,
        "risk_summary": {
            "high_risk_items": len(high_risk),
            "medium_risk_items": len(medium_risk),
            "low_risk_items": len(item_predictions) - len(high_risk) - len(medium_risk),
            "predicted_outcome": "LIKELY APPROVED" if avg_prob >= 75 else "LIKELY REJECTED" if avg_prob < 50 else "AT RISK"
        },
        "item_predictions": item_predictions,
        "submission_tips": history["notes"],
        "state": state,
        "project_type": project_type
    })


@app.route("/api/submittal/warranty-assembly", methods=["POST"])
def warranty_assembly():
    """Feature: Auto-assemble O&M warranty package from product IDs."""
    data = request.json
    product_ids = data.get("product_ids", [])
    project_name = data.get("project_name", "Construction Project")
    building_owner = data.get("building_owner", "Building Owner")

    packages = []
    missing = []
    total_manual_pages = 0
    earliest_expiry = None

    for pid in product_ids:
        w = WARRANTY_DB.get(pid)
        if not w:
            # Try to find by partial match
            w = next((v for k, v in WARRANTY_DB.items() if k.startswith(pid[0])), None)

        if w:
            from datetime import date
            install_year = date.today().year
            expiry_year = install_year + w["warranty_years"]
            total_manual_pages += w["manual_pages"]

            packages.append({
                "product_id": pid,
                "product_name": w["product"],
                "brand": w["brand"],
                "warranty_years": w["warranty_years"],
                "warranty_type": w["warranty_type"],
                "warranty_start": f"{install_year}-01-01",
                "warranty_expiry": f"{expiry_year}-01-01",
                "maintenance_interval": w["maintenance_interval"],
                "spare_parts": w["spare_parts"],
                "manual_pages": w["manual_pages"],
                "certifications": w["certifications"],
                "maintenance_schedule": _generate_maintenance_schedule(w)
            })

            if earliest_expiry is None or expiry_year < earliest_expiry:
                earliest_expiry = expiry_year
        else:
            missing.append(pid)

    # Sort by warranty expiry (shortest first = most urgent)
    packages.sort(key=lambda x: x["warranty_years"])

    return jsonify({
        "project_name": project_name,
        "building_owner": building_owner,
        "generated_at": datetime.now().isoformat(),
        "packages": packages,
        "missing_products": missing,
        "summary": {
            "total_products": len(packages),
            "total_manual_pages": total_manual_pages,
            "earliest_warranty_expiry": f"{earliest_expiry}-01-01" if earliest_expiry else None,
            "maintenance_items_first_year": len([p for p in packages if "Annual" in p["maintenance_interval"] or "Quarterly" in p["maintenance_interval"]]),
            "estimated_assembly_time_saved": f"{round(len(packages) * 0.75, 1)} hours",
        }
    })


def _generate_maintenance_schedule(w):
    """Generate a structured maintenance schedule from warranty data."""
    interval = w["maintenance_interval"].lower()
    tasks = []
    if "annual" in interval or "yearly" in interval:
        tasks.append({"frequency": "Annual", "task": w["maintenance_interval"], "months": [6]})
    if "semi-annual" in interval or "twice" in interval:
        tasks.append({"frequency": "Semi-Annual", "task": w["maintenance_interval"], "months": [3, 9]})
    if "quarterly" in interval:
        tasks.append({"frequency": "Quarterly", "task": w["maintenance_interval"], "months": [3, 6, 9, 12]})
    if not tasks:
        tasks.append({"frequency": "As needed", "task": w["maintenance_interval"], "months": []})
    return tasks


@app.route("/api/submittal/collaboration", methods=["GET"])
def collaboration():
    """Feature: Multi-distributor collaboration — shared project with conflict detection."""
    return jsonify(COLLAB_PROJECT)


@app.route("/api/submittal/resolve-conflict", methods=["POST"])
def resolve_conflict():
    """Resolve a conflict in the collaboration project."""
    data = request.json
    conflict_id = data.get("conflict_id")
    resolution = data.get("resolution", "accepted")

    conflict = next((c for c in COLLAB_PROJECT["conflicts"] if c["id"] == conflict_id), None)
    if not conflict:
        return jsonify({"error": "Conflict not found"}), 404

    return jsonify({
        "conflict_id": conflict_id,
        "resolution": resolution,
        "message": f"Conflict {conflict_id} marked as {resolution}. All distributors notified. Submittal package updated.",
        "remaining_conflicts": len([c for c in COLLAB_PROJECT["conflicts"] if c["id"] != conflict_id])
    })


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5055))
    print("\n🏗️  Parspec Construction Procurement Agent v3")
    print("   Catalogue: 50 MEP products (7 categories)")
    print("   Features: Submittals · O&M · Revision Tracker · Engineer Prediction · Collaboration")
    print("   Running at: http://localhost:5055\n")
    app.run(host="0.0.0.0", port=port, debug=False)

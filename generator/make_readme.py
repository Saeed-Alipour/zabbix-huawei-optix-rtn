#!/usr/bin/env python3
"""Write README.md next to each generated template YAML, listing its macros, items, discovery rules,
triggers and graphs, so the documentation always matches the template.

Usage: python3 generator/make_readme.py      (from the repository root, after build_templates.py)
"""
import os, re
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TDIR = os.path.join(ROOT, "Network_Devices", "Huawei", "template_huawei_optix_rtn_snmp")
YAML = "template_huawei_optix_rtn_snmp.yaml"
BASE = "Huawei OptiX RTN by SNMP"
PRIO = {"INFO": "Info", "WARNING": "Warning", "AVERAGE": "Average", "HIGH": "High", "DISASTER": "Disaster"}


def cell(s):
    return str(s or "").replace("|", "\\|").replace("\n", " ").strip()


def short_expr(e, tname):
    return cell(e.replace(f"/{tname}/", "/TEMPLATE/"))


def intro(ver):
    return f"""# Huawei OptiX RTN by SNMP

## Overview

Templates for **Huawei OptiX RTN** microwave radios (RTN 905, 910A, 950A, 980 and 380H) for **Zabbix {ver}**, by SNMP.

They monitor:
- NE information: name, NE ID, IP, model, software version, uptime, NE state
- boards: working state, temperature against the board's own threshold, hardware, software and FPGA versions
- ODUs: RX and TX power, configured TX power, frequencies, T/R spacing, band, transmitter mute, bar code
- radio IF ports: RX/TX modulation, capacity, adaptive modulation and ATPC settings, channel bandwidth, link ID, far-end NE
- 15-minute radio performance: RSL/TSL min/avg/max, SNR, MSE, BER and FEC counters
- Ethernet and radio ports: traffic (instant rate and octet counters), utilization, drops and FCS errors
- active alarms from the NE alarm table (curAlmDataTable), as one problem per alarm with its location
- PTP (IEEE 1588) time synchronisation, PTP ports, system clock state
- PLA groups, IF 1+1 protection, control board (DPS) protection on the RTN 980
- E-LAN services and the VLANs on their ports

Ports, IFs and ODUs are named with their far-end NE name (learned over the radio link), or the port name configured on
the NE, e.g. `ODU 21 (IF 1/1, SITE-B)`.

The file holds six templates:

| Template | Link it to |
|---|---|
| Huawei OptiX RTN by SNMP | Any RTN NE (common items only) |
| Huawei OptiX RTN 905 by SNMP | RTN 905 |
| Huawei OptiX RTN 910A by SNMP | RTN 910A |
| Huawei OptiX RTN 950A by SNMP | RTN 950A |
| Huawei OptiX RTN 980 by SNMP | RTN 980 |
| Huawei OptiX RTN 380H by SNMP | RTN 380H |

Each model template links the base template and adds the items only that model supports (fan, system clock, PLA,
IF 1+1, FEC; DPS on the RTN 980; PLL and far-end NE ID on the RTN 380H). Link **one** template per host: the model
template, or the base template if the model is not listed.

## Requirements

- Zabbix {ver}
- SNMP v2c access to the NE (read community), from the Zabbix server or proxy
- SNMP timeout of the server or proxy (`Timeout=` in zabbix_server.conf / zabbix_proxy.conf) of **15 seconds**: some NEs answer slowly
- Simple checks (ICMP ping) enabled: `fping` installed on the server or proxy

## Setup

1. Import `{YAML}` (Data collection > Templates > Import).
2. Create a host for the NE with an SNMP interface (the NE IP, SNMPv2, the `{{$SNMP_COMMUNITY}}` macro set to the read community).
3. Link the model template of the NE. The base template's item *Device model* shows the model if you are not sure.
4. Optional: tune the macros below on the host, e.g. a per-link RSL threshold `{{$RTN.ODU.RX.WARN:"21"}}` for ODU 21.

Discovery rules run about once an hour; use *Execute now* on a rule to fill a new host at once.

In the Zabbix 6.0 template every discovery rule has its own interval (3667 s, 3734 s, ...), so that the table walks of one
NE do not all run in the same second: Zabbix 6.0 schedules the items of one SNMP interface that share an interval at the
same time, and many RTN NEs answer such bursts with genError.

## Author

Saeed Alipour

## License

MIT
"""


def main():
    for ver in ("6.0", "7.0"):
        d = yaml.safe_load(open(os.path.join(TDIR, ver, YAML)))["zabbix_export"]
        out = [intro(ver)]
        for t in d["templates"]:
            name = t["template"]
            out.append(f"\n## Template: {name}\n\n{cell(t.get('description'))}\n")
            if t.get("macros"):
                out.append("### Macros\n\n| Macro | Default | Description |\n|---|---|---|")
                out += [f"| `{m['macro']}` | `{cell(m['value'])}` | {cell(m.get('description'))} |" for m in t["macros"]]
            items = [i for i in t.get("items", []) if i.get("history") != "0"]
            if items:
                out.append("\n### Items\n\n| Name | Key | Interval | Description |\n|---|---|---|---|")
                out += [f"| {cell(i['name'])} | `{i['key']}` | {i.get('delay', '1m') if i.get('type') != 'DEPENDENT' else 'dependent'} "
                        f"| {cell(i.get('description'))} |" for i in items]
            trig = [(tr, i["name"]) for i in t.get("items", []) for tr in i.get("triggers", [])] + \
                   [(tr, "") for tr in t.get("triggers", [])]
            if trig:
                out.append("\n### Triggers\n\n| Name | Severity | Expression |\n|---|---|---|")
                out += [f"| {cell(tr['name'])} | {PRIO[tr['priority']]} | `{short_expr(tr['expression'], name)}` |" for tr, _ in trig]
            for r in t.get("discovery_rules", []):
                out.append(f"\n### Discovery rule: {r['name']}\n\n{cell(r.get('description'))}\n")
                out.append("| Item prototype | Key | Interval | Description |\n|---|---|---|---|")
                out += [f"| {cell(p['name'])} | `{p['key']}` | {p.get('delay', '1m') if p.get('type') != 'DEPENDENT' else 'dependent'} "
                        f"| {cell(p.get('description'))} |" for p in r.get("item_prototypes", [])]
                tps = [tp for p in r.get("item_prototypes", []) for tp in p.get("trigger_prototypes", [])] + r.get("trigger_prototypes", [])
                if tps:
                    out.append("\n| Trigger prototype | Severity | Expression |\n|---|---|---|")
                    out += [f"| {cell(tp['name'])} | {PRIO[tp['priority']]} | `{short_expr(tp['expression'], name)}` |" for tp in tps]
                if r.get("graph_prototypes"):
                    out.append("\n| Graph prototype | Items |\n|---|---|")
                    out += [f"| {cell(g['name'])} | {', '.join('`' + gi['item']['key'] + '`' for gi in g['graph_items'])} |"
                            for g in r["graph_prototypes"]]
            gr = [g for g in d.get("graphs", []) if g["graph_items"][0]["item"]["host"] == name]
            if gr:
                out.append("\n### Graphs\n\n| Graph | Items |\n|---|---|")
                out += [f"| {cell(g['name'])} | {', '.join('`' + gi['item']['key'] + '`' for gi in g['graph_items'])} |" for g in gr]
        open(os.path.join(TDIR, ver, "README.md"), "w").write("\n".join(out).rstrip() + "\n")
        print(os.path.relpath(os.path.join(TDIR, ver, "README.md"), ROOT))


if __name__ == "__main__":
    main()

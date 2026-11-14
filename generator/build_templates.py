#!/usr/bin/env python3
"""Generate the Zabbix templates for Huawei OptiX RTN microwave radios, for Zabbix 6.0 and 7.0.

Every item is defined once below and rendered for both versions. Both use classic SNMP items
(the poller bundles them into bulk requests) and discovery[] LLD rules; in 7.0 the small
active-alarm table is walked once a minute with walk[] and feeds the alarm items and counters.

Templates: one base template that works on every model, plus one per model that links the
base and adds what only that model (family) supports. OIDs, index layouts, units and value
meanings were checked against SNMP walks of RTN 905, 910A, 950A, 980 and 380H NEs.

Usage: python3 generator/build_templates.py      (from the repository root; needs PyYAML)
Writes Network_Devices/Huawei/template_huawei_optix_rtn_snmp/<6.0|7.0>/template_huawei_optix_rtn_snmp.yaml
"""
import hashlib, json, os, re
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "Network_Devices", "Huawei", "template_huawei_optix_rtn_snmp")
OUT_NAME = "template_huawei_optix_rtn_snmp.yaml"
HW = "1.3.6.1.4.1.2011.2.25"
BASE = "Huawei OptiX RTN by SNMP"
GROUP = "Templates/Network devices"

def uid(*parts):
    """Stable UUIDv4-formatted id from a name path, so re-generating keeps the same UUIDs."""
    h = list(hashlib.md5("|".join(("huawei-optix-rtn",) + parts).encode()).hexdigest())
    h[12] = "4"
    h[16] = "89ab"[int(h[16], 16) % 4]
    return "".join(h)

# ----------------------------------------------------------------------------- value maps
# Enumerations taken from the Huawei OPTIX MIBs (OPTIX-RTN-IF-MIB, OPTIX-GLOBAL-TC-MIB): value -> name
ENUMS = json.load(open(os.path.join(ROOT, "generator", "data", "optix_enums.json")))

def enum_from_catalog(obj):
    return {int(k): v for k, v in ENUMS[obj].items()}

def alarm_names():
    return {int(k): v for k, v in ENUMS["alarmEID"].items()}

def mod_label(name):
    # mode2048QAM -> 2048QAM, modeQPSKSTRONG -> QPSK Strong, modeBPSK500M -> BPSK 500M
    n = name[4:] if name.startswith("mode") else name
    n = re.sub(r"(?i)strong", " Strong", n)
    n = re.sub(r"(?i)light", " Light", n)
    n = re.sub(r"(\D)(\d+P?\d*M)$", r"\1 \2", n).replace("P5M", ".5M")
    return n.strip()

ALARMS = alarm_names()
VALUEMAPS = {
    "Huawei RTN modulation": {0: "Not in use", **{k: mod_label(v) for k, v in enum_from_catalog("optixRtnIFPortCurrRxMode").items()}},
    "Huawei RTN board state": {0: "Not working", 1: "Working"},
    "Huawei RTN fan speed": {1: "Low", 2: "Medium", 3: "High", 4: "Stopped", 5: "Auto low", 6: "Auto medium", 7: "Auto high", 9: "Auto"},
    "Huawei RTN ODU transmitter": {0: "Muted", 1: "Unmuted"},
    "Huawei RTN device type": {76: "RTN 910", 77: "RTN 950", 83: "RTN 980", 92: "RTN 310", 95: "RTN 905", 114: "RTN 950A",
                               115: "RTN 380", 138: "RTN 360", 140: "RTN 980L", 151: "RTN 320", 152: "RTN 910A",
                               160: "RTN 380H", 180: "RTN 380E", 183: "RTN 905E", 191: "PowerCube 500", 203: "RTN 380A",
                               206: "RTN 380AX"},
    "Huawei RTN NE state": {0: "Installing", 1: "Running"},
    "Huawei RTN alarm severity": {1: "Critical", 2: "Major", 3: "Minor", 4: "Warning", 5: "Not reported"},
    "Huawei RTN clock work mode": {1: "Tracing", 2: "Holdover", 3: "Free-run"},
    "Huawei RTN PLL lock": {0: "Unlocked", 1: "Locked"},
    "Huawei RTN PTP lock": {0: "Unlocked", 1: "Locked"},
    "Huawei RTN PTP clock state": {0: "Free-run", 1: "Locked", 2: "Holdover out of spec"},
    "Huawei RTN PTP source mode": {1: "Physical clock", 2: "PTP", 3: "PTP ACR unicast"},
    "Huawei RTN PTP port state": {1: "Initializing", 2: "Faulty", 3: "Disabled", 4: "Listening", 5: "Pre-master", 6: "Master",
                                  7: "Passive", 8: "Uncalibrated", 9: "Slave", 255: "Unknown"},
    "Huawei RTN PLA status": {0: "Normal", 1: "Abnormal", 2: "Inhibited", 3: "Uni-normal", -1: "Unknown"},
    "Huawei RTN PLA unit role": {0: "Slave", 1: "Master", -1: "Unknown"},
    "Huawei RTN 1+1 board state": {0: "Normal", 1: "Failed", 2: "RDI switching", -1: "Unknown"},
    "Huawei RTN 1+1 switch request": {0: "Normal", 1: "Automatic", 2: "Manual", 3: "Forced", 4: "Lockout", 5: "Wait to restore", 6: "RDI"},
    "Huawei RTN DPS state": {1: "Adding", 2: "Deleting", 3: "Active"},
    "Huawei RTN link state": {0: "Down", 1: "Up"},
    "Huawei RTN alarm": {k: v for k, v in ALARMS.items()},
    "Huawei RTN enable state": {0: "Disabled", 1: "Enabled"},
    "Huawei RTN E-LAN tag mode": {0: "Tag-aware", 1: "C-Aware", 2: "S-Aware"},
    "Huawei RTN AM modulation": {0: "None (AM disabled)", **{k: mod_label(v) for k, v in enum_from_catalog("optixRtnIFPortCurrRxMode").items()}},
    "Huawei RTN channel bandwidth": {k: re.sub(r"^(FCC)?(\d+)P?(\d*)M(ACCP)?$",
                                               lambda m: (m[1] + " " if m[1] else "") + m[2] + ("." + m[3] if m[3] else "")
                                               + " MHz" + (" ACCP" if m[4] else ""), v[2:])
                                     for k, v in enum_from_catalog("optixRtnIFPortChannelBandWidth").items()},
}

# JavaScript helpers shared by the LLD rules (Duktape, ES5)
JS_LIB = r"""
function rows(value) {
    var d = JSON.parse(value), r = Array.isArray(d) ? d : (d.data || []);
    // a Zabbix 7 walk can carry "No Such Instance/Object ..." for a column the NE lacks: treat it as absent
    r.forEach(function (o) {
        for (var k in o) if (/^No Such (Instance|Object)/.test(String(o[k]))) delete o[k];
    });
    return r;
}
// index "26.26.98.111..." or "26.98.111..." -> the ASCII string it encodes
function idxString(idx) {
    var p = String(idx).split('.');
    for (var i = 0; i < p.length; i++) {
        if (p.length - i - 1 === parseInt(p[i], 10)) {
            var s = '';
            for (var j = i + 1; j < p.length; j++) s += String.fromCharCode(parseInt(p[j], 10));
            return s;
        }
    }
    return String(idx);
}
// "board=17,subcard=255,port=5" -> {board: 17, subcard: 255, port: 5}
function location(s) {
    var o = {};
    String(s).split(',').forEach(function (kv) {
        var a = kv.split('=');
        if (a.length === 2) o[a[0].trim()] = parseInt(a[1], 10);
    });
    return o;
}
// ODU slot -> IF slot/port: +20/+40 on RTN 905/910A/950A, +50/+70 on RTN 980, same slot on RTN 380H
function oduIf(slot) {
    var b = [[70, 2], [50, 1], [40, 2], [20, 1]];
    for (var i = 0; i < b.length; i++)
        if (slot > b[i][0]) return [slot - b[i][0], b[i][1]];
    return [slot, 1];
}
function oduName(slot) {
    var p = oduIf(slot);
    return 'ODU ' + slot + ' (IF ' + p[0] + '/' + p[1] + ')';
}
// Destination of a port: the neighbour NE name the radio learns over the link ({#P.NB}),
// else the port name engineers typed on the NE ({#P.NAME}). Both tables are indexed slot.255.port
// and arrive as extra discovery rows next to the rule's own rows.
// factory-default port labels (RTN 380H and others) name the port type, not a destination
var DEFAULT_PORT_NAMES = /^(IF|P&E|COMBO(\(e\))?|\d*0?GE\d*|NMS)$/i;
function labels(R) {
    var L = {};
    R.forEach(function (r) {
        var nb = String(r['{#P.NB}'] || '').trim(), pn = String(r['{#P.NAME}'] || '').trim();
        if (DEFAULT_PORT_NAMES.test(pn)) pn = '';
        if (nb || pn) L[String(r['{#SNMPINDEX}'])] = nb || pn;
    });
    return function (slot, port) { return L[slot + '.255.' + port] || ''; };
}
function withName(id, n) { return n ? id + ' (' + n + ')' : id; }
function oduLabel(slot, lab) {
    var p = oduIf(slot), n = lab(p[0], p[1]);
    return 'ODU ' + slot + ' (IF ' + p[0] + '/' + p[1] + (n ? ', ' + n : '') + ')';
}
"""
PN_COL = f"{HW}.4.30.36.1.1.1.2"         # optixPortname: name typed on the port
NB_COL = f"{HW}.4.40.3.10.92.1.2"       # optixRtnNeighbourNeName: far-end NE name learned over the link
NAME_COLS = [("{#P.NAME}", PN_COL), ("{#P.NB}", NB_COL)]

def js(body):
    return (JS_LIB + body).strip() + "\n"

# ----------------------------------------------------------------------------- item model
def item(name, key, oid, vt="UNSIGNED", units="", pre=(), vmap=None, delay="{$RTN.INTERVAL.STATUS}",
         desc="", tags=(("component", "system"),), triggers=(), inventory=None, kind="snmp", history=None):
    return dict(name=name, key=key, oid=oid, vt=vt, units=units, pre=list(pre), vmap=vmap, delay=delay,
                desc=desc, tags=list(tags), triggers=list(triggers), inventory=inventory, kind=kind, history=history)

def trig(name, expr, prio, desc="", deps=(), manual=False, tags=()):
    return dict(name=name, expr=expr, prio=prio, desc=desc, deps=list(deps), manual=manual, tags=list(tags))

def proto(name, key, col, **kw):
    """Item prototype: value from table column <col>.<index>[<suffix>] (or a calculated formula)."""
    suffix = kw.pop("suffix", "")
    formula = kw.pop("formula", None)
    it = item(name, key, None, **kw)
    it["col"], it["suffix"], it["formula"] = col, suffix, formula
    return it

def lld(name, key, cols, script, protos, delay, walk_extra=(), filters=(), lifetime="7d", desc="",
        trig_protos=(), graphs=(), walk=None, walk_delay=None):
    """cols: [(macro, column OID)] the discovery reads; script: JS body that returns the LLD JSON."""
    return dict(name=name, key=key, cols=list(cols), script=script, protos=list(protos), delay=delay,
                walk_extra=list(walk_extra), filters=list(filters), lifetime=lifetime, desc=desc,
                trig_protos=list(trig_protos), graphs=list(graphs), walk=walk, walk_delay=walk_delay)

X01 = [("MULTIPLIER", "0.1")]
# Daily inventory values (board versions, ODU bar codes) are stored at every poll: Latest data only shows
# values from the last 24 h. 23h, not 1d, so a poll that runs a few seconds early is not discarded.
VERSION_KEEP = "23h"
DBM = dict(vt="FLOAT", units="dBm", pre=X01)

# ----------------------------------------------------------------------------- base template
def base_template():
    T = "{T}"
    items = [
        item("NE name", "rtn.ne.name", f"{HW}.4.30.21.1.1.0", vt="CHAR", delay="{$RTN.INTERVAL.INVENTORY}",
             desc="NE name configured on the device (optixNeName). sysName is always \"Optix product\" on these radios.",
             inventory="NAME", pre=[("DISCARD_UNCHANGED_HEARTBEAT", "1d")]),
        item("NE ID", "rtn.ne.id", f"{HW}.3.40.2.1.1.0", delay="{$RTN.INTERVAL.INVENTORY}",
             desc="NE ID (optixNeID). Extended ID = value / 65536, basic ID = value % 65536.",
             pre=[("DISCARD_UNCHANGED_HEARTBEAT", "1d")]),
        item("NE IP address", "rtn.ne.ip", f"{HW}.3.40.2.2.1.0", vt="CHAR", delay="{$RTN.INTERVAL.INVENTORY}",
             desc="NE IP address (optixNeIP).", pre=[("DISCARD_UNCHANGED_HEARTBEAT", "1d")]),
        item("Device model", "rtn.ne.model", f"{HW}.4.30.21.1.8.0", vmap="Huawei RTN device type",
             delay="{$RTN.INTERVAL.INVENTORY}", desc="Device type (optixNeDeviceType).",
             pre=[("DISCARD_UNCHANGED_HEARTBEAT", "1d")]),
        item("NE state", "rtn.ne.state", f"{HW}.4.30.21.1.7.0", vmap="Huawei RTN NE state",
             desc="NE status (optixNeState): installing or running.",
             triggers=[trig("NE is not in running state", f"last(/{T}/rtn.ne.state)=0", "AVERAGE",
                            "The NE reports the install state (optixNeState=0), e.g. during a software load.")]),
        item("Software version", "rtn.ne.software", "1.3.6.1.2.1.1.1.0", vt="CHAR", delay="{$RTN.INTERVAL.INVENTORY}",
             desc="sysDescr. Many NEs leave it empty; where set it holds the software version (e.g. V100R019C10SPC300).",
             inventory="OS", pre=[("DISCARD_UNCHANGED_HEARTBEAT", "1d")]),
        item("Uptime", "rtn.ne.uptime", "1.3.6.1.2.1.1.3.0", vt="FLOAT", units="uptime", pre=[("MULTIPLIER", "0.01")],
             desc="sysUpTime. Note: the 32-bit counter wraps after 497 days, which looks like a restart.",
             triggers=[trig("Device has been restarted (uptime < 10m)", f"last(/{T}/rtn.ne.uptime)<10m", "WARNING",
                            "Uptime is under 10 minutes. A sysUpTime wrap after 497 days also triggers this.", manual=True)]),
        item("SNMP agent availability", "zabbix[host,snmp,available]", None, kind="internal", delay="1m",
             vmap=None, desc="Zabbix internal check: 0 = SNMP not available, 1 = available.",
             triggers=[trig("No SNMP data collection", f"max(/{T}/zabbix[host,snmp,available],{{$SNMP.TIMEOUT}})=0", "AVERAGE",
                            "The SNMP agent has not answered for {$SNMP.TIMEOUT}.",
                            deps=[("Unavailable by ICMP ping", f"max(/{T}/icmpping,#3)=0")])]),
        item("ICMP ping", "icmpping", None, kind="simple", delay="1m", tags=[("component", "health")],
             triggers=[trig("Unavailable by ICMP ping", f"max(/{T}/icmpping,#3)=0", "HIGH",
                            "Last three ICMP checks failed.")]),
        item("ICMP loss", "icmppingloss", None, kind="simple", vt="FLOAT", units="%", delay="1m", tags=[("component", "health")],
             triggers=[trig("High ICMP ping loss", f"min(/{T}/icmppingloss,5m)>{{$RTN.ICMP.LOSS.WARN}} and min(/{T}/icmppingloss,5m)<100",
                            "WARNING", deps=[("Unavailable by ICMP ping", f"max(/{T}/icmpping,#3)=0")])]),
        item("ICMP response time", "icmppingsec", None, kind="simple", vt="FLOAT", units="s", delay="1m", tags=[("component", "health")],
             triggers=[trig("High ICMP ping response time", f"avg(/{T}/icmppingsec,5m)>{{$RTN.ICMP.RESPONSE.WARN}}", "WARNING",
                            deps=[("High ICMP ping loss", f"min(/{T}/icmppingloss,5m)>{{$RTN.ICMP.LOSS.WARN}} and min(/{T}/icmppingloss,5m)<100"),
                                  ("Unavailable by ICMP ping", f"max(/{T}/icmpping,#3)=0")])]),
    ]

    BRD = f"{HW}.4.30.14.1"
    boards = lld(
        "Board discovery", "rtn.board.discovery", [("{#BOARD.TYPE}", f"{BRD}.1.1.2"), ("{#BOARD.STATE}", f"{BRD}.2.1.3")],
        js("""
var out = [];
rows(value).forEach(function (r) {
    // configured but physically absent boards (BdStatus alarm) have no physical state row
    if (r['{#BOARD.STATE}'] === undefined || r['{#BOARD.STATE}'] === '') return;
    out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}'], '{#BOARD.SLOT}': r['{#SNMPINDEX}'],
              '{#BOARD.TYPE}': String(r['{#BOARD.TYPE}']).toUpperCase(),
              '{#BOARD.NAME}': 'Slot ' + r['{#SNMPINDEX}'] + ' (' + String(r['{#BOARD.TYPE}']).toUpperCase() + ')'});
});
return JSON.stringify(out);"""),
        [proto("{#BOARD.NAME}: State", "rtn.board.state[{#SNMPINDEX}]", f"{BRD}.2.1.3", vmap="Huawei RTN board state",
               tags=[("component", "board"), ("board", "{#BOARD.NAME}")], desc="Board working status (optixPhyBoardState).",
               triggers=[trig("{#BOARD.NAME}: Board is not working", "last(/{T}/rtn.board.state[{#SNMPINDEX}])=0", "HIGH",
                              "optixPhyBoardState reports notWork(0).")])],
        delay="{$RTN.INTERVAL.STATUS}", walk_extra=[f"{BRD}.2.1.3"], desc="Boards in the subrack (optixLogBoardTable).")

    # optixPhyBDVerInfo is one multi-line string per board, e.g.
    #   "PCB      Version : SL91ISM6 VER.E\r\nSoftware Version : 1.38\r\nFPGA     Version : (U16)104\r\n"
    # (ODUs report only the software line). One entity per line present, so no item stays empty.
    versions = lld(
        "Board version discovery", "rtn.board.version.discovery",
        [("{#BOARD.TYPE}", f"{BRD}.1.1.2"), ("{#BOARD.VER}", f"{BRD}.2.1.7")],
        js("""
var FIELDS = [[/PCB\\s+Version\\s*:/, 'PCB', 'hw', 'Hardware'], [/Software\\s+Version\\s*:/, 'Software', 'sw', 'Software'],
              [/FPGA\\s+Version\\s*:/, 'FPGA', 'fpga', 'FPGA']];
var out = [];
rows(value).forEach(function (r) {
    var v = r['{#BOARD.VER}'];
    if (v === undefined || v === '' || r['{#BOARD.TYPE}'] === undefined) return;
    var name = 'Slot ' + r['{#SNMPINDEX}'] + ' (' + String(r['{#BOARD.TYPE}']).toUpperCase() + ')';
    FIELDS.forEach(function (f) {
        if (!f[0].test(v)) return;
        out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}'], '{#BOARD.NAME}': name,
                  '{#VER.RE}': f[1], '{#VER.KEY}': f[2], '{#VER.FIELD}': f[3]});
    });
});
return JSON.stringify(out);"""),
        [proto("{#BOARD.NAME}: {#VER.FIELD} version", "rtn.board.version[{#SNMPINDEX},{#VER.KEY}]", f"{BRD}.2.1.7", vt="CHAR",
               delay="{$RTN.INTERVAL.VERSION}", tags=[("component", "inventory"), ("board", "{#BOARD.NAME}")],
               desc="{#VER.FIELD} version of the board, from its version information (optixPhyBDVerInfo).",
               pre=[("JAVASCRIPT", """// the agent may return the string as hex bytes ("50 43 42 ...")
if (/^([0-9A-F]{2}\\s+)+[0-9A-F]{0,2}\\s*$/i.test(value) && value.indexOf(':') < 0)
    value = value.trim().split(/\\s+/).map(function (h) { return String.fromCharCode(parseInt(h, 16)); }).join('');
var m = value.match(/{#VER.RE}\\s+Version\\s*:\\s*([^\\r\\n]+)/);
if (!m) throw 'no {#VER.RE} version line in: ' + value;
return m[1].trim();"""), ("DISCARD_UNCHANGED_HEARTBEAT", VERSION_KEEP)],
               triggers=[trig("{#BOARD.NAME}: {#VER.FIELD} version changed",
                              f"change(/{T}/rtn.board.version[{{#SNMPINDEX}},{{#VER.KEY}}])=1", "INFO",
                              "The board reports a different version than before: a software upgrade or a replaced board.",
                              manual=True)])],
        delay="{$RTN.INTERVAL.VERSION}", desc="Hardware (PCB), software and FPGA version of each board (optixPhyBDVerInfo).")

    temps = lld(
        "Board temperature discovery", "rtn.board.temp.discovery",
        [("{#BOARD.TYPE}", f"{BRD}.1.1.2"), ("{#BOARD.TEMP}", f"{BRD}.1.1.5")],
        js("""
var out = [];
rows(value).forEach(function (r) {
    if (r['{#BOARD.TEMP}'] === undefined || isNaN(parseFloat(r['{#BOARD.TEMP}']))) return;
    out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}'],
              '{#BOARD.NAME}': 'Slot ' + r['{#SNMPINDEX}'] + ' (' + String(r['{#BOARD.TYPE}']).toUpperCase() + ')'});
});
return JSON.stringify(out);"""),
        [proto("{#BOARD.NAME}: Temperature", "rtn.board.temp[{#SNMPINDEX}]", f"{BRD}.1.1.5", vt="FLOAT", units="°C",
               tags=[("component", "environment"), ("board", "{#BOARD.NAME}")], desc="Board temperature (optixLogBoardCurTemp).",
               triggers=[
                   trig("{#BOARD.NAME}: Temperature is above the board's high threshold",
                        "min(/{T}/rtn.board.temp[{#SNMPINDEX}],5m)>=last(/{T}/rtn.board.temp.high[{#SNMPINDEX}])", "HIGH",
                        "The board's own high-temperature threshold (optixLogBoardTempHighTh) has been reached."),
                   trig("{#BOARD.NAME}: Temperature is near the board's high threshold",
                        "min(/{T}/rtn.board.temp[{#SNMPINDEX}],5m)>=last(/{T}/rtn.board.temp.high[{#SNMPINDEX}])-{$RTN.TEMP.MARGIN}",
                        "WARNING", "Within {$RTN.TEMP.MARGIN} °C of the board's high threshold.",
                        deps=[("{#BOARD.NAME}: Temperature is above the board's high threshold",
                               "min(/{T}/rtn.board.temp[{#SNMPINDEX}],5m)>=last(/{T}/rtn.board.temp.high[{#SNMPINDEX}])")])]),
         proto("{#BOARD.NAME}: Temperature high threshold", "rtn.board.temp.high[{#SNMPINDEX}]", f"{BRD}.1.1.3", vt="FLOAT",
               units="°C", delay="{$RTN.INTERVAL.INVENTORY}", tags=[("component", "environment"), ("board", "{#BOARD.NAME}")],
               desc="Upper temperature threshold set on the board (optixLogBoardTempHighTh).")],
        delay="{$RTN.INTERVAL.STATUS}", walk_extra=[f"{BRD}.1.1.3"], desc="Boards that report a temperature.",
        walk="rtn.board.walk")

    ODU = f"{HW}.4.40.4.10"
    def oname(primary):
        return js("""
var R = rows(value), lab = labels(R), out = [];
R.forEach(function (r) {
    if (r['%s'] === undefined) return;
    var slot = parseInt(String(r['{#SNMPINDEX}']).split('.')[0], 10);
    out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}'], '{#ODU.SLOT}': slot, '{#ODU.ID}': oduName(slot), '{#ODU.NAME}': oduLabel(slot, lab)});
});
return JSON.stringify(out);""" % primary)
    otag = [("component", "radio"), ("odu", "{#ODU.NAME}")]
    rx_key = "rtn.odu.rx.power[{#SNMPINDEX}]"
    nosig = trig("{#ODU.NAME}: No received signal", f"max(/{T}/{rx_key},3m)<{{$RTN.ODU.RX.NOSIGNAL}}", "HIGH",
                 "Received power is below {$RTN.ODU.RX.NOSIGNAL} dBm: the link is most likely down.")
    odus = lld(
        "ODU discovery", "rtn.odu.discovery", [("{#ODU.RX}", f"{ODU}.30.1.9")] + NAME_COLS, oname("{#ODU.RX}"),
        [proto("{#ODU.NAME}: RX power", rx_key, f"{ODU}.30.1.9", delay="{$RTN.INTERVAL.RADIO}", tags=otag, **DBM,
               desc="Actual received power, RSL (optixRtnOduActualRxPower, 0.1 dBm).",
               triggers=[nosig,
                         trig("{#ODU.NAME}: Low received signal level",
                              f'max(/{T}/{rx_key},5m)<{{$RTN.ODU.RX.WARN:"{{#ODU.SLOT}}"}}', "WARNING",
                              "RSL below {$RTN.ODU.RX.WARN} dBm for 5 minutes. Set the macro per link with context, "
                              "with the ODU number, e.g. {$RTN.ODU.RX.WARN:27}.",
                              deps=[(nosig["name"], nosig["expr"])]),
                         trig("{#ODU.NAME}: RX power dropped below its daily average",
                              f"avg(/{T}/{rx_key},10m)<avg(/{T}/{rx_key},1d)-{{$RTN.ODU.RX.DROP}}", "WARNING",
                              "RSL over the last 10 minutes is {$RTN.ODU.RX.DROP} dB or more below the 1-day average "
                              "(rain fade, misalignment or a fault at the far end).",
                              deps=[(nosig["name"], nosig["expr"])])]),
         proto("{#ODU.NAME}: TX power", "rtn.odu.tx.power[{#SNMPINDEX}]", f"{ODU}.30.1.8", delay="{$RTN.INTERVAL.RADIO}",
               tags=otag, **DBM, desc="Actual transmit power (optixRtnOduActualTxPower, 0.1 dBm)."),
         proto("{#ODU.NAME}: TX power, configured", "rtn.odu.tx.power.cfg[{#SNMPINDEX}]", f"{ODU}.30.1.1",
               delay="{$RTN.INTERVAL.INVENTORY}", tags=otag, vt="FLOAT", units="dBm",
               pre=X01 + [("DISCARD_UNCHANGED_HEARTBEAT", "1d")], desc="Configured transmit power (optixRtnOduCfgTxPower)."),
         proto("{#ODU.NAME}: Power to be received", "rtn.odu.rx.power.expected[{#SNMPINDEX}]", f"{ODU}.30.1.2",
               delay="{$RTN.INTERVAL.INVENTORY}", tags=otag, vt="FLOAT", units="dBm",
               pre=X01 + [("DISCARD_UNCHANGED_HEARTBEAT", "1d")],
               desc="Receive power the RF port is configured to expect (optixRtnOduCfgToBeRxPower)."),
         proto("{#ODU.NAME}: TX frequency", "rtn.odu.tx.freq[{#SNMPINDEX}]", f"{ODU}.20.1.3", delay="{$RTN.INTERVAL.INVENTORY}",
               tags=otag, units="Hz", pre=[("MULTIPLIER", "1000"), ("DISCARD_UNCHANGED_HEARTBEAT", "1d")],
               desc="Actual transmit frequency (optixRtnOduActualTxFreq, kHz).",
               triggers=[trig("{#ODU.NAME}: TX frequency changed", f"change(/{T}/rtn.odu.tx.freq[{{#SNMPINDEX}}])<>0", "INFO",
                              manual=True)]),
         proto("{#ODU.NAME}: RX frequency", "rtn.odu.rx.freq[{#SNMPINDEX}]", f"{ODU}.20.1.4", delay="{$RTN.INTERVAL.INVENTORY}",
               tags=otag, units="Hz", pre=[("MULTIPLIER", "1000"), ("DISCARD_UNCHANGED_HEARTBEAT", "1d")],
               desc="Actual receive frequency (optixRtnOduActualRxFreq, kHz)."),
         proto("{#ODU.NAME}: T/R spacing", "rtn.odu.trspacing[{#SNMPINDEX}]", f"{ODU}.20.1.2", delay="{$RTN.INTERVAL.INVENTORY}",
               tags=otag, units="Hz", pre=[("MULTIPLIER", "1000"), ("DISCARD_UNCHANGED_HEARTBEAT", "1d")],
               desc="Configured transmit/receive spacing (optixRtnOduCfgTRSpacing, kHz)."),
        ],
        delay="{$RTN.INTERVAL.RADIO}", desc="Outdoor units (optixRtnOduPowerTable, deprecated MIB module that all firmware supports).",
        graphs=[("{#ODU.NAME}: RX and TX power", [rx_key, "rtn.odu.tx.power[{#SNMPINDEX}]"]),
                ("{#ODU.NAME}: TX and RX frequency", ["rtn.odu.tx.freq[{#SNMPINDEX}]", "rtn.odu.rx.freq[{#SNMPINDEX}]"]),
                ("{#ODU.NAME}: T/R spacing", ["rtn.odu.trspacing[{#SNMPINDEX}]"])])
    odu_barcode = lld(
        "ODU barcode discovery", "rtn.odu.barcode.discovery", [("{#ODU.BARCODE}", f"{ODU}.13.1.1")] + NAME_COLS,
        oname("{#ODU.BARCODE}"),
        [proto("{#ODU.NAME}: Barcode", "rtn.odu.barcode[{#SNMPINDEX}]", f"{ODU}.13.1.1", vt="CHAR",
               delay="{$RTN.INTERVAL.VERSION}", tags=[("component", "inventory"), ("odu", "{#ODU.NAME}")],
               pre=[("DISCARD_UNCHANGED_HEARTBEAT", VERSION_KEEP)], desc="ODU bar code / serial number (optixRtnOduFactoryInfo).",
               triggers=[trig("{#ODU.NAME}: ODU was replaced (barcode changed)",
                              f"change(/{T}/rtn.odu.barcode[{{#SNMPINDEX}}])=1", "INFO", manual=True)])],
        delay="{$RTN.INTERVAL.VERSION}", desc="ODU bar codes (not reported by every ODU).")
    # Some RTN 950A with old firmware lack the ODU band and actual-state tables: each gets its own
    # rule keyed on its column, so items are only created where the NE reports them.
    odu_band = lld(
        "ODU frequency band discovery", "rtn.odu.band.discovery", [("{#ODU.BAND}", f"{ODU}.101.1.1")] + NAME_COLS, oname("{#ODU.BAND}"),
        [proto("{#ODU.NAME}: Frequency band", "rtn.odu.band[{#SNMPINDEX}]", f"{ODU}.101.1.1", delay="{$RTN.INTERVAL.INVENTORY}",
               tags=otag, units="GHz", pre=[("DISCARD_UNCHANGED_HEARTBEAT", "1d")],
               desc="ODU frequency band (optixRtnOduFreqBand).")],
        delay="{$RTN.INTERVAL.RADIO}", walk="rtn.odu.walk", desc="ODUs that report their frequency band.")
    odu_state = lld(
        "ODU transmitter state discovery", "rtn.odu.state.discovery", [("{#ODU.TXSTATE}", f"{ODU}.40.1.2")] + NAME_COLS, oname("{#ODU.TXSTATE}"),
        [proto("{#ODU.NAME}: Transmitter state", "rtn.odu.tx.state[{#SNMPINDEX}]", f"{ODU}.40.1.2", delay="{$RTN.INTERVAL.STATUS}",
               tags=otag, vmap="Huawei RTN ODU transmitter",
               desc="Actual transmitter state (optixRtnOduActualWorkState): muted or unmuted.",
               triggers=[trig("{#ODU.NAME}: Transmitter is muted", f"last(/{T}/rtn.odu.tx.state[{{#SNMPINDEX}}])=0", "AVERAGE",
                              "The ODU transmitter is muted, so this end sends no signal.")])],
        delay="{$RTN.INTERVAL.RADIO}", walk="rtn.odu.walk", desc="ODUs that report their actual transmitter state.")

    IFT = f"{HW}.4.40.3.10.50.1"
    itag = [("component", "radio"), ("if", "{#IF.NAME}")]
    ifs = lld(
        "Radio IF discovery", "rtn.if.discovery", [("{#IF.RXMODE}", f"{IFT}.2")] + NAME_COLS,
        js("""
var R = rows(value), lab = labels(R), out = [];
R.forEach(function (r) {
    if (r['{#IF.RXMODE}'] === undefined || String(r['{#IF.RXMODE}']) === '0') return;   // not an IF row / port not in use
    var p = String(r['{#SNMPINDEX}']).split('.'), id = 'IF ' + p[0] + '/' + p[p.length - 1];
    out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}'], '{#IF.ID}': id, '{#IF.NAME}': withName(id, lab(p[0], p[p.length - 1]))});
});
return JSON.stringify(out);"""),
        [proto("{#IF.NAME}: RX modulation", "rtn.if.rx.mode[{#SNMPINDEX}]", f"{IFT}.2", vmap="Huawei RTN modulation",
               delay="{$RTN.INTERVAL.RADIO}", tags=itag, desc="Current receive modulation (optixRtnIFPortCurrRxMode).",
               triggers=[trig("{#IF.NAME}: Radio link down (no modulation)", f"last(/{T}/rtn.if.rx.mode[{{#SNMPINDEX}}])=0", "HIGH",
                              "The IF port reports no receive modulation."),
                         trig("{#IF.NAME}: RX modulation changed", f"change(/{T}/rtn.if.rx.mode[{{#SNMPINDEX}}])<>0", "INFO",
                              "Adaptive modulation changed the receive mode.", manual=True)]),
         proto("{#IF.NAME}: TX modulation", "rtn.if.tx.mode[{#SNMPINDEX}]", f"{IFT}.1", vmap="Huawei RTN modulation",
               delay="{$RTN.INTERVAL.RADIO}", tags=itag, desc="Current transmit modulation (optixRtnIFPortCurrTxMode)."),
         proto("{#IF.NAME}: RX capacity", "rtn.if.rx.capacity[{#SNMPINDEX}]", f"{IFT}.6", units="bps",
               pre=[("MULTIPLIER", "1000000")], delay="{$RTN.INTERVAL.RADIO}", tags=itag,
               desc="Current receive service capacity with adaptive modulation (optixRtnIFPortAMCurrRxRate, Mbit/s).",
               triggers=[trig("{#IF.NAME}: Running below full capacity (modulation downshift)",
                              f"max(/{T}/rtn.if.rx.capacity[{{#SNMPINDEX}}],10m)<last(/{T}/rtn.if.capacity.peak[{{#SNMPINDEX}}]) "
                              f"and last(/{T}/rtn.if.rx.capacity[{{#SNMPINDEX}}])>0", "WARNING",
                              "Receive capacity has been below the full AM capacity for 10 minutes (fading or interference).")]),
         proto("{#IF.NAME}: TX capacity", "rtn.if.tx.capacity[{#SNMPINDEX}]", f"{IFT}.5", units="bps",
               pre=[("MULTIPLIER", "1000000")], delay="{$RTN.INTERVAL.RADIO}", tags=itag,
               desc="Current transmit service capacity (optixRtnIFPortAMCurrSendRate, Mbit/s)."),
         proto("{#IF.NAME}: Full capacity", "rtn.if.capacity.peak[{#SNMPINDEX}]", f"{IFT}.4", units="bps",
               pre=[("MULTIPLIER", "1000000"), ("DISCARD_UNCHANGED_HEARTBEAT", "1d")], delay="{$RTN.INTERVAL.INVENTORY}",
               tags=itag, desc="Full AM service capacity (optixRtnIFPortAMPeakRate, Mbit/s)."),
         proto("{#IF.NAME}: Guaranteed capacity", "rtn.if.capacity.guaranteed[{#SNMPINDEX}]", f"{IFT}.3", units="bps",
               pre=[("MULTIPLIER", "1000000"), ("DISCARD_UNCHANGED_HEARTBEAT", "1d")], delay="{$RTN.INTERVAL.INVENTORY}",
               tags=itag, desc="Guaranteed AM service capacity (optixRtnIFPortAMGuaranteeRate, Mbit/s).")],
        delay="{$RTN.INTERVAL.RADIO}", desc="Radio IF ports in use (modulation not 0).",
        graphs=[("{#IF.NAME}: Capacity", ["rtn.if.rx.capacity[{#SNMPINDEX}]", "rtn.if.tx.capacity[{#SNMPINDEX}]"]),
                ("{#IF.NAME}: Modulation", ["rtn.if.rx.mode[{#SNMPINDEX}]", "rtn.if.tx.mode[{#SNMPINDEX}]"])])

    # Radio IF settings: AM, ATPC and link ID tables share the IF index (slot.255.port). Polled hourly in their
    # own rules so the 1-minute IF walk (v7) stays small. Only ports in use (modulation not 0), as in Radio IF discovery.
    def if_js(primary):
        return js("""
var R = rows(value), lab = labels(R), out = [];
R.forEach(function (r) {
    if (r['%s'] === undefined || r['{#IF.RXMODE}'] === undefined || String(r['{#IF.RXMODE}']) === '0') return;
    var p = String(r['{#SNMPINDEX}']).split('.'), id = 'IF ' + p[0] + '/' + p[p.length - 1];
    out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}'], '{#IF.ID}': id, '{#IF.NAME}': withName(id, lab(p[0], p[p.length - 1]))});
});
return JSON.stringify(out);""" % primary)
    IFAM, ATPC = f"{HW}.4.40.3.10.40.1", f"{HW}.4.40.1.10.1.1"
    inv = dict(delay="{$RTN.INTERVAL.INVENTORY}", tags=itag)
    keep = [("DISCARD_UNCHANGED_HEARTBEAT", "1d")]
    no_am = [("JAVASCRIPT", "// -1 on ports with adaptive modulation disabled\nreturn parseInt(value, 10) < 0 ? 0 : value;")] + keep
    if_cfg = lld(
        "Radio IF settings discovery", "rtn.if.cfg.discovery", [("{#IF.AM}", f"{IFAM}.2"), ("{#IF.RXMODE}", f"{IFT}.2")] + NAME_COLS,
        if_js("{#IF.AM}"),
        [proto("{#IF.NAME}: Link ID", "rtn.if.link.id[{#SNMPINDEX}]", f"{HW}.4.40.3.10.20.1.1", pre=keep, **inv,
               desc="Radio link ID configured on the port (optixRtnIFPortCfgLinkID). Both ends of a link must use the same ID."),
         proto("{#IF.NAME}: AM status", "rtn.if.am.state[{#SNMPINDEX}]", f"{IFAM}.2", vmap="Huawei RTN enable state", pre=keep, **inv,
               desc="Adaptive modulation enabled or disabled (optixRtnIFPortAMEnableStatus)."),
         proto("{#IF.NAME}: Min modulation", "rtn.if.am.min[{#SNMPINDEX}]", f"{IFAM}.3", vmap="Huawei RTN AM modulation", pre=no_am, **inv,
               desc="Lowest modulation adaptive modulation may use (optixRtnIFPortAMBottomMod). 0 when AM is disabled (the NE reports -1)."),
         proto("{#IF.NAME}: Max modulation", "rtn.if.am.max[{#SNMPINDEX}]", f"{IFAM}.4", vmap="Huawei RTN AM modulation", pre=no_am, **inv,
               desc="Highest modulation adaptive modulation may use (optixRtnIFPortAMPeakMod). 0 when AM is disabled (the NE reports -1)."),
         proto("{#IF.NAME}: ATPC", "rtn.if.atpc.state[{#SNMPINDEX}]", f"{ATPC}.1", vmap="Huawei RTN enable state", pre=keep, **inv,
               desc="Automatic transmit power control enabled or disabled (optixRtnIFATPCEnableState)."),
         proto("{#IF.NAME}: ATPC upper threshold", "rtn.if.atpc.high[{#SNMPINDEX}]", f"{ATPC}.3", vt="FLOAT", units="dBm",
               pre=X01 + keep, **inv, desc="ATPC upper RSL threshold (optixRtnIFATPCHighThreshold, 0.1 dBm)."),
         proto("{#IF.NAME}: ATPC lower threshold", "rtn.if.atpc.low[{#SNMPINDEX}]", f"{ATPC}.4", vt="FLOAT", units="dBm",
               pre=X01 + keep, **inv, desc="ATPC lower RSL threshold (optixRtnIFATPCLowThreshold, 0.1 dBm).")],
        delay="{$RTN.INTERVAL.INVENTORY}", desc="Link ID, adaptive modulation and ATPC settings of the radio IF ports in use.")
    if_bw = lld(
        "Radio IF channel bandwidth discovery", "rtn.if.bw.discovery", [("{#IF.BW}", f"{IFT}.16"), ("{#IF.RXMODE}", f"{IFT}.2")] + NAME_COLS,
        if_js("{#IF.BW}"),
        [proto("{#IF.NAME}: Channel bandwidth", "rtn.if.bw[{#SNMPINDEX}]", f"{IFT}.16", vmap="Huawei RTN channel bandwidth",
               pre=keep, **inv, desc="Radio channel bandwidth (optixRtnIFPortChannelBandWidth).")],
        delay="{$RTN.INTERVAL.INVENTORY}", desc="IF ports that report their channel bandwidth (not RTN 380H and some old RTN 950A firmware).")

    nbr = lld(
        "Radio link neighbour discovery", "rtn.if.nb.discovery", [("{#P.NB}", NB_COL), ("{#P.NAME}", PN_COL)],
        js("""
var R = rows(value), lab = labels(R), out = [];
R.forEach(function (r) {
    if (!String(r['{#P.NB}'] || '').trim()) return;   // only ports where the radio reports a far-end NE
    var p = String(r['{#SNMPINDEX}']).split('.'), id = 'IF ' + p[0] + '/' + p[p.length - 1];
    out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}'], '{#IF.ID}': id, '{#IF.NAME}': withName(id, lab(p[0], p[p.length - 1]))});
});
return JSON.stringify(out);"""),
        [proto("{#IF.NAME}: Far-end NE", "rtn.if.farend[{#SNMPINDEX}]", NB_COL, vt="CHAR", delay="{$RTN.INTERVAL.STATUS}",
               tags=itag, desc="Name of the NE at the other end of this radio link, as the radio learns it over the air "
                               "(optixRtnNeighbourNeName). The port name typed on the NE is not always up to date.",
               triggers=[trig("{#IF.ID}: Far-end NE changed to {ITEM.LASTVALUE}",
                              f"change(/{T}/rtn.if.farend[{{#SNMPINDEX}}])=1 and length(last(/{T}/rtn.if.farend[{{#SNMPINDEX}}]))>0",
                              "WARNING", "This radio link now reaches a different NE: wrong pointing, a swapped radio or a "
                              "reconfiguration.", manual=True)])],
        delay="{$RTN.INTERVAL.STATUS}", desc="Radio ports that report a far-end NE name.")

    IFPM = f"{HW}.3.70.10.70.60.1.2"
    def pm_js(primary, fields):
        return js("""
var R = rows(value), lab = labels(R), out = [];
R.forEach(function (r) {
    if (r['%s'] === undefined) return;
    var idx = String(r['{#SNMPINDEX}']);
    var loc = location(idxString(idx));
    if (loc.board === undefined) return;
    out.push({'{#SNMPINDEX}': idx, %s});
});
return JSON.stringify(out);""" % (primary, fields))
    IF_FIELDS = "'{#IF.ID}': 'IF ' + loc.board + '/' + loc.port, '{#IF.NAME}': withName('IF ' + loc.board + '/' + loc.port, lab(loc.board, loc.port))"
    ODU_FIELDS = "'{#ODU.ID}': oduName(loc.board), '{#ODU.NAME}': oduLabel(loc.board, lab)"
    PORT_FIELDS = "'{#PORT.SP}': loc.board + '/' + loc.port, '{#PORT.ID}': 'Port ' + loc.board + '/' + loc.port, '{#PORT.NAME}': withName('Port ' + loc.board + '/' + loc.port, lab(loc.board, loc.port))"
    pmtag = [("component", "radio"), ("if", "{#IF.NAME}")]
    def ifpm(n, key, eid, units="dB", pre=X01, desc=""):
        return proto("{#IF.NAME}: " + n, f"rtn.if.pm.{key}[{{#SNMPINDEX}}]", f"{IFPM}.{eid}", vt="FLOAT", units=units,
                     pre=pre, delay="{$RTN.INTERVAL.PM}", tags=pmtag, desc=desc + " Current 15-minute PM period.")
    ifpms = lld(
        "Radio IF performance discovery", "rtn.if.pm.discovery", [("{#IF.SNR}", f"{IFPM}.15377")] + NAME_COLS,
        pm_js("{#IF.SNR}", IF_FIELDS),
        [ifpm("SNR, min", "snr.min", 15376, desc="Minimum SNR (pmIfSnrMin, 0.1 dB)."),
         ifpm("SNR, avg", "snr.avg", 15377, desc="Average SNR (pmIfSnrAvg, 0.1 dB)."),
         ifpm("SNR, max", "snr.max", 15375, desc="Maximum SNR (pmIfSnrMax, 0.1 dB)."),
         ifpm("MSE, avg", "mse.avg", 15507, desc="Average MSE (pmIfMseAvg, 0.1 dB)."),
         ifpm("MSE, worst", "mse.max", 15508, desc="Highest (worst) MSE (pmIfMseMax, 0.1 dB)."),
         ifpm("MSE, best", "mse.min", 15509, desc="Lowest (best) MSE (pmIfMseMin, 0.1 dB)."),
         ifpm("BER", "ber", 15479, units="", pre=[], desc="Bit error rate counter (pmIfBer).")],
        delay="{$RTN.INTERVAL.PM}", desc="Radio IF performance: SNR, MSE and BER of the current 15-minute period.",
        graphs=[("{#IF.NAME}: SNR", ["rtn.if.pm.snr.min[{#SNMPINDEX}]", "rtn.if.pm.snr.avg[{#SNMPINDEX}]", "rtn.if.pm.snr.max[{#SNMPINDEX}]"]),
                ("{#IF.NAME}: MSE", ["rtn.if.pm.mse.min[{#SNMPINDEX}]", "rtn.if.pm.mse.avg[{#SNMPINDEX}]",
                                     "rtn.if.pm.mse.max[{#SNMPINDEX}]"])])

    ODPM = f"{HW}.3.70.10.80.60.1.2"
    optag = [("component", "radio"), ("odu", "{#ODU.NAME}")]
    def odpm(n, key, eid, desc):
        return proto("{#ODU.NAME}: " + n, f"rtn.odu.pm.{key}[{{#SNMPINDEX}}]", f"{ODPM}.{eid}", delay="{$RTN.INTERVAL.PM}",
                     tags=optag, desc=desc + " Current 15-minute PM period.", **DBM)
    odpms = lld(
        "ODU performance discovery", "rtn.odu.pm.discovery", [("{#ODU.RSL}", f"{ODPM}.8608")] + NAME_COLS,
        pm_js("{#ODU.RSL}", ODU_FIELDS),
        [odpm("RSL, min", "rsl.min", 8607, "Minimum received signal level (pmRslMin, 0.1 dBm)."),
         odpm("RSL, avg", "rsl.avg", 15043, "Average received signal level (pmRslAvg, 0.1 dBm)."),
         odpm("RSL, max", "rsl.max", 8606, "Maximum received signal level (pmRslMax, 0.1 dBm)."),
         odpm("TSL, min", "tsl.min", 8610, "Minimum transmit signal level (pmTslMin, 0.1 dBm)."),
         odpm("TSL, avg", "tsl.avg", 15047, "Average transmit signal level (pmTslAvg, 0.1 dBm)."),
         odpm("TSL, max", "tsl.max", 8609, "Maximum transmit signal level (pmTslMax, 0.1 dBm).")],
        delay="{$RTN.INTERVAL.PM}", desc="ODU performance: RSL and TSL of the current 15-minute period.",
        trig_protos=[trig("{#ODU.NAME}: Fading: RSL dipped {$RTN.RSL.FADE} dB below average in this 15-minute period",
                          "last(/{T}/rtn.odu.pm.rsl.avg[{#SNMPINDEX}])-last(/{T}/rtn.odu.pm.rsl.min[{#SNMPINDEX}])>{$RTN.RSL.FADE}",
                          "WARNING", "The 15-minute minimum RSL is more than {$RTN.RSL.FADE} dB under the 15-minute average.")],
        graphs=[("{#ODU.NAME}: RSL (15-minute min/avg/max)", ["rtn.odu.pm.rsl.min[{#SNMPINDEX}]", "rtn.odu.pm.rsl.avg[{#SNMPINDEX}]",
                                                             "rtn.odu.pm.rsl.max[{#SNMPINDEX}]"])])

    ETH = f"{HW}.3.70.20.102.100.1.4"
    etag = [("component", "network"), ("port", "{#PORT.NAME}")]
    def eth(n, key, ev, units, pre, desc, delay="{$RTN.INTERVAL.TRAFFIC}", vt="FLOAT", trg=()):
        return proto("{#PORT.NAME}: " + n, f"rtn.eth.{key}[{{#SNMPINDEX}}]", f"{ETH}.{ev}", vt=vt, units=units, pre=pre,
                     delay=delay, tags=etag, desc=desc, triggers=trg)
    def util_t(d):
        hi = trig("{#PORT.NAME}: " + d.upper() + " utilization above {$RTN.ETH.UTIL.HIGH}%",
                  f"min(/{T}/rtn.eth.util.{d}[{{#SNMPINDEX}}],{{$RTN.ETH.UTIL.PERIOD}})>{{$RTN.ETH.UTIL.HIGH:\"{{#PORT.SP}}\"}}",
                  "AVERAGE", "Utilization has been above {$RTN.ETH.UTIL.HIGH}% for {$RTN.ETH.UTIL.PERIOD}.")
        warn = trig("{#PORT.NAME}: " + d.upper() + " utilization above {$RTN.ETH.UTIL.WARN}%",
                    f"min(/{T}/rtn.eth.util.{d}[{{#SNMPINDEX}}],{{$RTN.ETH.UTIL.PERIOD}})>{{$RTN.ETH.UTIL.WARN:\"{{#PORT.SP}}\"}}",
                    "WARNING", "Utilization has been above {$RTN.ETH.UTIL.WARN}% for {$RTN.ETH.UTIL.PERIOD}.",
                    deps=[(hi["name"], hi["expr"])])
        return [hi, warn]
    eths = lld(
        "Ethernet port discovery", "rtn.eth.discovery", [("{#PORT.TXOCT}", f"{ETH}.199")] + NAME_COLS,
        pm_js("{#PORT.TXOCT}", PORT_FIELDS),
        [eth("Bits received", "in", 200, "bps", [("CHANGE_PER_SECOND", ""), ("MULTIPLIER", "8")],
             "Received bits per second, averaged from the cumulative RX octet counter (pmRXOCTETS). The NE can stop updating "
             "the counter for 1-2 minutes and then catch up, so single values can be too low and then too high: use RX rate (instant) "
             "for current traffic."),
         eth("Bits sent", "out", 199, "bps", [("CHANGE_PER_SECOND", ""), ("MULTIPLIER", "8")],
             "Sent bits per second, averaged from the cumulative TX octet counter (pmTXOCTETS). The NE can stop updating "
             "the counter for 1-2 minutes and then catch up, so single values can be too low and then too high: use TX rate (instant) "
             "for current traffic."),
         eth("RX rate (instant)", "in.rate", 679, "bps", [], "Instant receive rate reported by the NE (pmRXBPS)."),
         eth("TX rate (instant)", "out.rate", 680, "bps", [], "Instant transmit rate reported by the NE (pmTXBPS).")],
        delay="{$RTN.INTERVAL.TRAFFIC}", desc="Ethernet and radio ports with performance monitoring (ethPortPmCurTable).",
        # the graph uses the NE's own rate: the octet counters can stall for 1-2 minutes and then catch up at once, so
        # a rate computed from them dips and then overshoots (above the physical link rate)
        graphs=[("{#PORT.NAME}: Traffic", ["rtn.eth.in.rate[{#SNMPINDEX}]", "rtn.eth.out.rate[{#SNMPINDEX}]"])])
    # Not every port reports every counter (e.g. radio IF ports on some firmware have no FCS/drop counters):
    # one rule per counter, keyed on that counter, so items exist only where the NE has the value.
    def eth_rule(name, key, ev, protos, desc):
        return lld(name, key, [("{#PORT.EV}", f"{ETH}.{ev}")] + NAME_COLS, pm_js("{#PORT.EV}", PORT_FIELDS), protos,
                   delay="{$RTN.INTERVAL.TRAFFIC}",
                   walk="rtn.eth.walk", desc=desc)
    eth_util = eth_rule(
        "Ethernet port utilization discovery", "rtn.eth.util.discovery", 567,
        [eth("RX utilization", "util.rx", 567, "%", [("MULTIPLIER", "0.01")], "Receive bandwidth utilization (pmPORTRXBWUTILIZATION, 0.01 %).",
             trg=util_t("rx")),
         eth("TX utilization", "util.tx", 568, "%", [("MULTIPLIER", "0.01")], "Transmit bandwidth utilization (pmPORTTXBWUTILIZATION, 0.01 %).",
             trg=util_t("tx"))],
        "Ports that report bandwidth utilization.")
    eth_drop_in = eth_rule(
        "Ethernet port RX drop discovery", "rtn.eth.drop.in.discovery", 869,
        [eth("RX dropped packets", "drop.in", 869, "pps", [("CHANGE_PER_SECOND", "")], "Received packets dropped (pmRXDROPPKTS).")],
        "Ports that report received packet drops.")
    eth_drop_out = eth_rule(
        "Ethernet port TX drop discovery", "rtn.eth.drop.out.discovery", 868,
        [eth("TX dropped packets", "drop.out", 868, "pps", [("CHANGE_PER_SECOND", "")], "Transmit packets dropped (pmTXDROPPKTS).")],
        "Ports that report transmitted packet drops.")
    eth_fcs = eth_rule(
        "Ethernet port FCS discovery", "rtn.eth.fcs.discovery", 132,
        [eth("FCS errors", "fcs", 132, "", [("CHANGE_PER_SECOND", "")], "Frames with FCS errors per second (pmETHFCS).",
             trg=[trig("{#PORT.NAME}: FCS errors", f"min(/{T}/rtn.eth.fcs[{{#SNMPINDEX}}],5m)>0", "WARNING",
                       "Frames with CRC errors are arriving on this port (cabling, SFP or duplex problem).")])],
        "Ports that report FCS errors.")

    ALM = f"{HW}.3.40.30.10.10.1"
    atag = [("component", "alarm"), ("alarm", "{#ALM.NAME}")]
    akey = "rtn.alarm.severity[{#SNMPINDEX}]"
    def alarm_t(sev, label, prio):
        return trig(f"{{#ALM.NAME}} ({{#ALM.LOCATION}}) [{label}]",
                    f"last(/{T}/{akey})={sev} and nodata(/{T}/{akey},{{$RTN.ALARM.NODATA}})=0"
                    f" and count(/{T}/{akey},{{$RTN.ALARM.MIN.ACTIVE}})>={{$RTN.ALARM.MIN.SAMPLES}}", prio,
                    "Active alarm on the NE (curAlmDataTable). It opens once the alarm has been seen in "
                    "{$RTN.ALARM.MIN.SAMPLES} polls within {$RTN.ALARM.MIN.ACTIVE} (the alarm item is polled every minute), "
                    "so short flaps do not raise problems. It clears when the alarm leaves the table.")
    alarm_js = "var NAMES = " + __import__("json").dumps({str(k): v for k, v in ALARMS.items()}, separators=(",", ":")) + ";\n" + """
var out = [], seen = {};
rows(value).forEach(function (r) {
    var eid = String(r['{#ALM.EID}']);
    var name = NAMES[eid] ? NAMES[eid].replace(/^alm/, '') : 'Alarm ' + eid;
    // curAlmPara: "<location>;<detail>;" e.g. "board=7,subcard=255,port=1;0x1;"
    var parts = String(r['{#ALM.PARA}'] || '').split(';');
    var loc = parts[0] || 'NE', detail = (parts[1] || '').trim();
    var key = eid + '|' + loc;
    seen[key] = (seen[key] || 0) + 1;
    out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}'], '{#ALM.EID}': eid, '{#ALM.SEV}': String(r['{#ALM.SEV}']),
              '{#ALM.NAME}': name, '{#ALM.LOCATION}': loc, _key: key, _detail: detail});
});
// the same alarm can be raised more than once on one location (e.g. per PoE channel):
// add the alarm detail to the location so every problem name is distinct
out.forEach(function (o) {
    if (seen[o._key] > 1) o['{#ALM.LOCATION}'] += ' ' + (o._detail || '#' + o['{#SNMPINDEX}']);
    delete o._key;
    delete o._detail;
});
return JSON.stringify(out);"""
    alarms = lld(
        "Active alarm discovery", "rtn.alarm.discovery",
        [("{#ALM.EID}", f"{ALM}.2"), ("{#ALM.SEV}", f"{ALM}.3"), ("{#ALM.PARA}", f"{ALM}.9")],
        js(alarm_js),
        [proto("Alarm {#ALM.NAME} ({#ALM.LOCATION}): Severity", akey, f"{ALM}.3", vmap="Huawei RTN alarm severity",
               delay="1m", tags=atag, desc="Severity of an active alarm (curAlmSeverity). Alarm ID {#ALM.EID}.",
               triggers=[alarm_t(1, "critical", "HIGH"), alarm_t(2, "major", "AVERAGE"), alarm_t(3, "minor", "WARNING")])],
        delay="{$RTN.INTERVAL.ALARM}", lifetime="1h", walk_delay="1m",
        filters=[("{#ALM.EID}", "NOT_MATCHES_REGEX", "{$RTN.ALARM.EID.IGNORE}"), ("{#ALM.SEV}", "MATCHES_REGEX", "^[123]$")],
        desc="One entity per active critical/major/minor alarm (curAlmDataTable). Alarm IDs matching "
             "{$RTN.ALARM.EID.IGNORE} are skipped.")

    # PTP (IEEE 1588 time sync): NE-level values are scalars (index 0), discovered only where PTP is enabled
    PTP = f"{HW}.4.50.13"
    ptp = lld(
        "PTP discovery", "rtn.ptp.discovery", [("{#PTP.ENABLE}", f"{PTP}.1.20")],
        js("""
var out = [];
rows(value).forEach(function (r) {
    if (String(r['{#PTP.ENABLE}']) !== '1') return;
    out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}']});
});
return JSON.stringify(out);"""),
        [proto("PTP time lock state", "rtn.ptp.time.lock[{#SNMPINDEX}]", f"{PTP}.2.3", vmap="Huawei RTN PTP lock",
               tags=[("component", "clock")], desc="PTP time lock state (optixPktPtpTimeLockState)."),
         proto("PTP clock state", "rtn.ptp.clock.state[{#SNMPINDEX}]", f"{PTP}.2.5", vmap="Huawei RTN PTP clock state",
               tags=[("component", "clock")], desc="PTP clock tracking state (optixPktPtpClockState): free-run, locked or holdover out of spec."),
         proto("PTP frequency lock state", "rtn.ptp.freq.lock[{#SNMPINDEX}]", f"{PTP}.2.2", vmap="Huawei RTN PTP lock",
               tags=[("component", "clock")], desc="PTP clock (frequency) lock state (optixPktPtpLockState)."),
         proto("PTP source mode", "rtn.ptp.src.mode[{#SNMPINDEX}]", f"{PTP}.1.6", vmap="Huawei RTN PTP source mode",
               delay="{$RTN.INTERVAL.INVENTORY}", tags=[("component", "clock")],
               desc="Time source mode (optixPktPtpSrcMode): PTP, or the physical clock (no time source).",
               pre=[("DISCARD_UNCHANGED_HEARTBEAT", "1d")]),
         proto("PTP grandmaster ID (high)", "rtn.ptp.gm.high[{#SNMPINDEX}]", f"{PTP}.1.17", delay="{$RTN.INTERVAL.STATUS}",
               tags=[("component", "clock")], desc="Upper 32 bits of the grandmaster clock ID (optixPktPtpGrandMasterGrandmasterID1).",
               pre=[("DISCARD_UNCHANGED_HEARTBEAT", "1d")]),
         proto("PTP grandmaster ID (low)", "rtn.ptp.gm.low[{#SNMPINDEX}]", f"{PTP}.1.18", delay="{$RTN.INTERVAL.STATUS}",
               tags=[("component", "clock")], desc="Lower 32 bits of the grandmaster clock ID (optixPktPtpGrandMasterGrandmasterID2).",
               pre=[("DISCARD_UNCHANGED_HEARTBEAT", "1d")])],
        delay="{$RTN.INTERVAL.STATUS}", desc="PTP (IEEE 1588) time synchronisation, on NEs where it is enabled.",
        trig_protos=[trig("PTP clock is not locked",
                          f"((count(/{T}/rtn.ptp.clock.state[{{#SNMPINDEX}}],{{$RTN.CLOCK.PERIOD}},\"eq\",1)=0 and count(/{T}/rtn.ptp.clock.state[{{#SNMPINDEX}}],{{$RTN.CLOCK.PERIOD}})>0) or "
                          f"(count(/{T}/rtn.ptp.time.lock[{{#SNMPINDEX}}],{{$RTN.CLOCK.PERIOD}},\"eq\",1)=0 and count(/{T}/rtn.ptp.time.lock[{{#SNMPINDEX}}],{{$RTN.CLOCK.PERIOD}})>0)) and {{$RTN.CLOCK.ALERT}}=1",
                          "AVERAGE", "The NE has not been locked to a PTP time source for {$RTN.CLOCK.PERIOD} "
                          "(clock state free-run or holdover out of spec, or time unlocked). "
                          "Set {$RTN.CLOCK.ALERT}=0 on a host that runs without a time source by design.")])
    ptp_ports = lld(
        "PTP port discovery", "rtn.ptp.port.discovery", [("{#PTP.PORT}", f"{PTP}.1.22.1.3"), ("{#PTP.REAL}", f"{PTP}.1.22.1.29")] + NAME_COLS,
        js("""
var R = rows(value), lab = labels(R), out = [];
R.forEach(function (r) {
    // rows of the name tables have no PTP column; ports with PTP disabled are skipped
    if (String(r['{#PTP.PORT}']) !== '1') return;
    // some NEs report PTP enabled on a port but have no state row for it (GET gives "No Such Instance")
    if (r['{#PTP.REAL}'] === undefined || r['{#PTP.REAL}'] === '') return;
    var p = String(r['{#SNMPINDEX}']).split('.');
    if (p.length !== 3) return;
    var id = 'PTP port ' + p[0] + '/' + p[2];
    out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}'], '{#PTP.PORT.NAME}': withName(id, lab(p[0], p[2]))});
});
return JSON.stringify(out);"""),
        [proto("{#PTP.PORT.NAME}: State", "rtn.ptp.port.state[{#SNMPINDEX}]", f"{PTP}.1.22.1.29", vmap="Huawei RTN PTP port state",
               tags=[("component", "clock"), ("ptp-port", "{#PTP.PORT.NAME}")],
               desc="PTP port state (optixPktPtpClockRealState): master, slave, passive, faulty, ...",
               triggers=[trig("{#PTP.PORT.NAME}: PTP port is faulty",
                              f"(count(/{T}/rtn.ptp.port.state[{{#SNMPINDEX}}],{{$RTN.CLOCK.PERIOD}},\"ne\",2)=0 and count(/{T}/rtn.ptp.port.state[{{#SNMPINDEX}}],{{$RTN.CLOCK.PERIOD}})>0) and {{$RTN.CLOCK.ALERT}}=1",
                              "WARNING", "The PTP port has been in the faulty state for {$RTN.CLOCK.PERIOD}.")]),
         proto("{#PTP.PORT.NAME}: Link state", "rtn.ptp.port.link[{#SNMPINDEX}]", f"{PTP}.1.22.1.15", vmap="Huawei RTN link state",
               tags=[("component", "clock"), ("ptp-port", "{#PTP.PORT.NAME}")], desc="PTP port link state (optixPktPtpClockLinkState).")],
        delay="{$RTN.INTERVAL.STATUS}", desc="Ports with PTP enabled (optixPktPtpClockTable).")

    # E-LAN (multipoint Ethernet) services, as in Web LCT Ethernet Service Management > E-LAN Service.
    # Service table index = service; UNI table index = service.uni. Polled daily: configuration only.
    ELAN, ELUNI = f"{HW}.4.50.3.1.4.1", f"{HW}.4.50.3.1.5.1"
    svc = dict(delay="{$RTN.INTERVAL.SERVICE}", pre=[("DISCARD_UNCHANGED_HEARTBEAT", VERSION_KEEP)])
    elan = lld(
        "E-LAN service discovery", "rtn.elan.discovery", [("{#ELAN.NAME}", f"{ELAN}.3")],
        js("""
var out = [];
rows(value).forEach(function (r) {
    if (r['{#ELAN.NAME}'] === undefined) return;
    var id = 'E-LAN ' + r['{#SNMPINDEX}'];
    out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}'], '{#ELAN.ID}': id, '{#ELAN.LABEL}': withName(id, String(r['{#ELAN.NAME}']).trim())});
});
return JSON.stringify(out);"""),
        [proto("{#ELAN.LABEL}: Tag type", "rtn.elan.tagmode[{#SNMPINDEX}]", f"{ELAN}.7", vmap="Huawei RTN E-LAN tag mode",
               tags=[("component", "service"), ("service", "{#ELAN.LABEL}")], **svc,
               desc="Tag type of the E-LAN service (optixElanTagMode): tag-aware, C-aware or S-aware."),
         proto("{#ELAN.LABEL}: MAC address learning", "rtn.elan.maclearn[{#SNMPINDEX}]", f"{ELAN}.8", vmap="Huawei RTN enable state",
               tags=[("component", "service"), ("service", "{#ELAN.LABEL}")], **svc,
               desc="Self-learning of MAC addresses on the E-LAN service (optixElanMacLearnEnable).")],
        delay="{$RTN.INTERVAL.SERVICE}", desc="E-LAN (multipoint Ethernet) services configured on the NE (optixElanTable).")
    elan_uni = lld(
        "E-LAN UNI discovery", "rtn.elan.uni.discovery",
        [("{#UNI.SLOT}", f"{ELUNI}.2"), ("{#UNI.SUB}", f"{ELUNI}.3"), ("{#UNI.PORT}", f"{ELUNI}.4"),
         ("{#ELAN.NAME}", f"{ELAN}.3")] + NAME_COLS,
        js("""
var R = rows(value), lab = labels(R), svc = {}, out = [];
R.forEach(function (r) { if (r['{#ELAN.NAME}'] !== undefined) svc[String(r['{#SNMPINDEX}'])] = String(r['{#ELAN.NAME}']).trim(); });
R.forEach(function (r) {
    // UNI rows are indexed service.uni; service and port-name rows arrive here too
    var p = String(r['{#SNMPINDEX}']).split('.');
    if (r['{#UNI.SLOT}'] === undefined || r['{#UNI.PORT}'] === undefined || p.length !== 2) return;
    var s = r['{#UNI.SLOT}'], sub = String(r['{#UNI.SUB}']), port = r['{#UNI.PORT}'];
    var pid = 'Port ' + s + '/' + (sub !== '255' && sub !== 'undefined' ? sub + '/' : '') + port;
    out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}'], '{#ELAN.LABEL}': withName('E-LAN ' + p[0], svc[p[0]] || ''),
              '{#UNI.ID}': pid, '{#UNI.NAME}': withName(pid, lab(s, port))});
});
return JSON.stringify(out);"""),
        [proto("{#ELAN.LABEL}: {#UNI.NAME}: VLAN count", "rtn.elan.uni.vlans[{#SNMPINDEX}]", f"{ELUNI}.5",
               tags=[("component", "service"), ("service", "{#ELAN.LABEL}"), ("port", "{#UNI.NAME}")], **svc,
               desc="Number of VLANs this port carries in the E-LAN service (optixElanUniVlanNum)."),
         proto("{#ELAN.LABEL}: {#UNI.NAME}: VLANs", "rtn.elan.uni.vlanlist[{#SNMPINDEX}]", f"{ELUNI}.6", vt="CHAR",
               tags=[("component", "service"), ("service", "{#ELAN.LABEL}"), ("port", "{#UNI.NAME}")],
               delay="{$RTN.INTERVAL.SERVICE}",
               pre=[("JAVASCRIPT", """// optixElanUniVlanlist: 512-byte bitmap, first bit = VLAN 1. Zabbix returns it as hex bytes.
var h = String(value).replace(/^[A-Za-z-]+:\\s*/, '');
var b = /^[\\s0-9A-Fa-f]+$/.test(h) ? h.replace(/\\s+/g, '').match(/../g) || [] : [];
if (!b.length) for (var i = 0; i < h.length; i++) b.push(h.charCodeAt(i).toString(16));
var v = [];
b.forEach(function (x, n) {
    var byte = parseInt(x, 16);
    for (var k = 0; k < 8; k++) if (byte & (0x80 >> k)) v.push(n * 8 + k + 1);
});
// 3,8,11-12,14 as in Web LCT
var out = [];
for (var i = 0; i < v.length; i++) {
    var j = i;
    while (j + 1 < v.length && v[j + 1] === v[j] + 1) j++;
    out.push(j > i ? v[i] + '-' + v[j] : String(v[i]));
    i = j;
}
return out.length ? out.join(',') : 'none';"""), ("DISCARD_UNCHANGED_HEARTBEAT", VERSION_KEEP)],
               desc="VLANs this port carries in the E-LAN service, e.g. 3,8,11-12,14 (optixElanUniVlanlist).",
               triggers=[trig("{#ELAN.LABEL}: {#UNI.ID}: VLANs changed to {ITEM.LASTVALUE}",
                              f"change(/{T}/rtn.elan.uni.vlanlist[{{#SNMPINDEX}}])=1", "INFO",
                              "The VLAN list of this E-LAN port changed: a service reconfiguration.", manual=True)])],
        delay="{$RTN.INTERVAL.SERVICE}", desc="Ports (UNIs) of the E-LAN services and the VLANs they carry (optixElanUniTable).")

    macros = [
        ("{$RTN.INTERVAL.RADIO}", "1m", "Poll interval for radio values (ODU power, modulation, capacity)."),
        ("{$RTN.INTERVAL.TRAFFIC}", "5m", "Poll interval for Ethernet/radio port traffic."),
        ("{$RTN.INTERVAL.PM}", "5m", "Poll interval for 15-minute performance values (RSL/TSL, SNR, MSE)."),
        ("{$RTN.INTERVAL.STATUS}", "5m", "Poll interval for boards, temperatures and status values."),
        ("{$RTN.INTERVAL.ALARM}", "5m", "How often active alarms are discovered (Zabbix 6.0 template; each run loads the server's LLD workers)."),
        ("{$RTN.INTERVAL.INVENTORY}", "1h", "Poll interval for configuration and inventory values."),
        ("{$RTN.INTERVAL.VERSION}", "1d", "Poll interval for board versions and ODU bar codes."),
        ("{$RTN.INTERVAL.SERVICE}", "1d", "Poll interval for E-LAN service settings and port VLAN lists."),
        ("{$RTN.SNMP.TIMEOUT}", "15s", "Zabbix 7 template only: timeout of the active-alarm walk (walk[] item). All other "
                                       "items use classic OIDs, which take the proxy's Timeout= setting (set it to 15)."),
        ("{$RTN.ODU.RX.WARN}", "-65", "RSL (dBm) below which a warning is raised. Per ODU with the ODU number as context, e.g. {$RTN.ODU.RX.WARN:27}."),
        ("{$RTN.ODU.RX.NOSIGNAL}", "-85", "RSL (dBm) below which the link is considered down."),
        ("{$RTN.ODU.RX.DROP}", "10", "RSL drop (dB) below the 1-day average that raises a warning."),
        ("{$RTN.RSL.FADE}", "10", "Gap (dB) between 15-minute average and minimum RSL that counts as fading."),
        ("{$RTN.TEMP.MARGIN}", "10", "Warn when a board is within this many °C of its own high threshold."),
        ("{$RTN.ETH.UTIL.WARN}", "70", "Port utilization (%) that raises a Warning after {$RTN.ETH.UTIL.PERIOD}. Per port with slot/port as context, e.g. {$RTN.ETH.UTIL.WARN:17/5}."),
        ("{$RTN.ETH.UTIL.HIGH}", "80", "Port utilization (%) that raises an Average problem after {$RTN.ETH.UTIL.PERIOD}. Per port, e.g. {$RTN.ETH.UTIL.HIGH:17/5}."),
        ("{$RTN.ETH.UTIL.PERIOD}", "5m", "How long utilization must stay above a level before a problem opens."),
        ("{$RTN.ALARM.EID.IGNORE}", "^$",
         "Alarm IDs (curAlmEID) that never raise problems, as a regex. The default ignores nothing. Example for alarms "
         "that are often standing conditions: ^(13047|412|333)$ = almPassWordNeedChange, almPowerAbnormal "
         "(one power input not connected) and almClkNoTraceMode (clock free-run). The alarm value map lists every ID."),
        ("{$RTN.ALARM.MIN.ACTIVE}", "5m", "Flap protection: window in which an alarm must be seen {$RTN.ALARM.MIN.SAMPLES} times."),
        ("{$RTN.ALARM.MIN.SAMPLES}", "4", "Flap protection: polls (one per minute) an alarm must be seen in before its problem opens."),
        ("{$RTN.ALARM.NODATA}", "5m", "An alarm problem closes when its row has been gone from the alarm table this long."),
        ("{$RTN.CLOCK.ALERT}", "1", "1 = raise clock problems (system clock not tracing, PTP not locked, PTP port faulty). "
                                    "Set 0 on a host whose clock or time runs free by design."),
        ("{$RTN.CLOCK.PERIOD}", "10m", "How long a clock must stay out of the tracing/locked state before a problem opens."),
        ("{$RTN.ICMP.LOSS.WARN}", "20", "ICMP loss (%) warning threshold."),
        ("{$RTN.ICMP.RESPONSE.WARN}", "0.3", "ICMP response time (s) warning threshold."),
        ("{$SNMP.TIMEOUT}", "5m", "No SNMP answer for this long raises a problem."),
    ]
    desc = ("Huawei OptiX RTN microwave radios (RTN 905, 910A, 950A, 980, 380H) by SNMP.\n"
            "Common items for all models: NE info, boards and temperatures, ODU power and frequencies, "
            "IF modulation and capacity, 15-minute radio performance (RSL/TSL, SNR, MSE), "
            "Ethernet/radio port traffic and active alarms.\n"
            "Link the model template (e.g. 'Huawei OptiX RTN 950A by SNMP') instead of this one to get model-specific items too.\n"
            "OIDs from the Huawei OPTIX MIBs, checked against SNMP walks of RTN 905, 910A, 950A, 980 and 380H NEs.\n"
            "Set the SNMP timeout of the server or proxy (Timeout=) to 15 seconds: some NEs answer slowly.")
    return dict(name=BASE, desc=desc, items=items, llds=[boards, versions, temps, odus, odu_barcode, odu_band, odu_state, ifs, if_cfg, if_bw, nbr, ifpms, odpms, eths, eth_util, eth_drop_in, eth_drop_out, eth_fcs, ptp, ptp_ports, elan, elan_uni, alarms],
                graphs=[("ICMP response time and loss", ["icmppingsec", ("icmppingloss", "R")]),
                        ("Uptime", ["rtn.ne.uptime"])],
                macros=macros, links=[], tags=[("class", "network"), ("target", "huawei-rtn")])

# ----------------------------------------------------------------------------- model templates
def shelf_parts(T_models):
    """Items for the subrack models (RTN 905/910A/950A/980): fan, SDH clock, PLA, IF 1+1, FEC."""
    T = "{T}"
    items = [
        item("Fan speed", "rtn.fan.speed", f"{HW}.4.30.39.1.1.0", vmap="Huawei RTN fan speed",
             tags=[("component", "environment")], desc="Fan speed (optixFanSpeed).",
             triggers=[trig("Fan has stopped", f"last(/{T}/rtn.fan.speed)=4", "AVERAGE", "optixFanSpeed reports stop(4).")]),
    ]
    # the clock table is indexed by the system control board slot: 1 on RTN 905/910A, 7 on 950A, 15 or 20 on 980
    SYN = f"{HW}.4.10.48.1.1.1"
    clk = lld(
        "System clock discovery", "rtn.clock.discovery", [("{#CLK.MODE}", f"{SYN}.6")],
        js("""
var out = [];
rows(value).forEach(function (r) {
    if (r['{#CLK.MODE}'] === undefined) return;
    out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}']});
});
return JSON.stringify(out);"""),
        [proto("Clock work mode", "rtn.clock.mode[{#SNMPINDEX}]", f"{SYN}.6", vmap="Huawei RTN clock work mode",
               tags=[("component", "clock")],
               desc="System clock work mode (optixSdhSysSynWorkMode) on the control board in slot {#SNMPINDEX}: tracing, holdover or free-run.",
               triggers=[trig("Clock is not tracing (slot {#SNMPINDEX})",
                              f"(count(/{T}/rtn.clock.mode[{{#SNMPINDEX}}],{{$RTN.CLOCK.PERIOD}},\"eq\",1)=0 and count(/{T}/rtn.clock.mode[{{#SNMPINDEX}}],{{$RTN.CLOCK.PERIOD}})>0) and {{$RTN.CLOCK.ALERT}}=1",
                              "WARNING", "The system clock has not been tracing a reference for {$RTN.CLOCK.PERIOD} (holdover or free-run). "
                              "Set {$RTN.CLOCK.ALERT}=0 on a host whose clock runs free by design.")])],
        delay="{$RTN.INTERVAL.INVENTORY}", desc="System clock (one row, indexed by the control board slot).")
    PLA = f"{HW}.4.40.5.10.100.1"
    ptag = [("component", "protection"), ("pla", "{#PLA.NAME}")]
    pla = lld(
        "PLA group discovery", "rtn.pla.discovery", [("{#PLA.BOARD}", f"{PLA}.1"), ("{#PLA.PORT}", f"{PLA}.3")],
        js("""
var out = [];
rows(value).forEach(function (r) {
    out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}'],
              '{#PLA.NAME}': 'PLA ' + r['{#SNMPINDEX}'] + ' (main IF ' + r['{#PLA.BOARD}'] + '/' + r['{#PLA.PORT}'] + ')'});
});
return JSON.stringify(out);"""),
        [proto("{#PLA.NAME}: Main unit link status", "rtn.pla.main.link[{#SNMPINDEX}]", f"{PLA}.5", vmap="Huawei RTN PLA status",
               tags=ptag, desc="Link status of the main unit (optixRtnPhyLagPGMainLinkStatus).",
               triggers=[trig("{#PLA.NAME}: Main unit link is abnormal", f"last(/{T}/rtn.pla.main.link[{{#SNMPINDEX}}])=1", "AVERAGE")]),
         proto("{#PLA.NAME}: Main unit hardware status", "rtn.pla.main.hw[{#SNMPINDEX}]", f"{PLA}.4", vmap="Huawei RTN PLA status",
               tags=ptag, desc="Hardware status of the main unit (optixRtnPhyLagPGMainHardStatus)."),
         proto("{#PLA.NAME}: Main unit role", "rtn.pla.main.role[{#SNMPINDEX}]", f"{PLA}.6", vmap="Huawei RTN PLA unit role",
               tags=ptag, desc="Whether the main unit currently works as master (optixRtnPhyLagPGMainPuWorkStatus)."),
         proto("{#PLA.NAME}: Slave unit link status", "rtn.pla.slave.link[{#SNMPINDEX}]", f"{PLA}.12", vmap="Huawei RTN PLA status",
               tags=ptag, desc="Link status of slave unit 1 (optixRtnPhyLagPGStatePu1LinkStatus).",
               triggers=[trig("{#PLA.NAME}: Slave unit link is abnormal", f"last(/{T}/rtn.pla.slave.link[{{#SNMPINDEX}}])=1", "AVERAGE")])],
        delay="{$RTN.INTERVAL.STATUS}", desc="Physical link aggregation (PLA/EPLA) groups.")
    PG = f"{HW}.4.40.5.10.20.1"
    gtag = [("component", "protection"), ("pg", "IF 1+1 group {#SNMPINDEX}")]
    pg = lld(
        "IF 1+1 protection discovery", "rtn.if1p1.discovery", [("{#PG.WORK}", f"{PG}.1")],
        js("""
var out = [];
rows(value).forEach(function (r) { out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}']}); });
return JSON.stringify(out);"""),
        [proto("IF 1+1 group {#SNMPINDEX}: Working board state", "rtn.if1p1.work[{#SNMPINDEX}]", f"{PG}.4",
               vmap="Huawei RTN 1+1 board state", tags=gtag, desc="optixRtn1j1PGDevWorkBoardState.",
               triggers=[trig("IF 1+1 group {#SNMPINDEX}: Working board failed", f"last(/{T}/rtn.if1p1.work[{{#SNMPINDEX}}])=1", "AVERAGE")]),
         proto("IF 1+1 group {#SNMPINDEX}: Protection board state", "rtn.if1p1.prot[{#SNMPINDEX}]", f"{PG}.5",
               vmap="Huawei RTN 1+1 board state", tags=gtag, desc="optixRtn1j1PGDevProtectBoardState.",
               triggers=[trig("IF 1+1 group {#SNMPINDEX}: Protection board failed", f"last(/{T}/rtn.if1p1.prot[{{#SNMPINDEX}}])=1", "AVERAGE")]),
         proto("IF 1+1 group {#SNMPINDEX}: Switch request", "rtn.if1p1.request[{#SNMPINDEX}]", f"{PG}.6",
               vmap="Huawei RTN 1+1 switch request", tags=gtag, desc="optixRtn1j1PGDevSwtichRequest.",
               triggers=[trig("IF 1+1 group {#SNMPINDEX}: Protection switched", f"change(/{T}/rtn.if1p1.request[{{#SNMPINDEX}}])<>0",
                              "INFO", manual=True)]),
         proto("IF 1+1 group {#SNMPINDEX}: Current working board", "rtn.if1p1.active[{#SNMPINDEX}]", f"{PG}.1", tags=gtag,
               desc="Slot of the board currently carrying traffic (optixRtn1j1PGStateDevWorkBoardID).")],
        delay="{$RTN.INTERVAL.STATUS}", desc="IF 1+1 HSB/SD/FD protection groups.")
    IFPM = f"{HW}.3.70.10.70.60.1.2"
    fec = lld(
        "Radio IF FEC discovery", "rtn.if.fec.discovery", [("{#IF.FEC}", f"{IFPM}.252")] + NAME_COLS,
        js("""
var R = rows(value), lab = labels(R), out = [];
R.forEach(function (r) {
    if (r['{#IF.FEC}'] === undefined) return;
    var loc = location(idxString(r['{#SNMPINDEX}']));
    if (loc.board === undefined) return;
    var id = 'IF ' + loc.board + '/' + loc.port;
    out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}'], '{#IF.ID}': id, '{#IF.NAME}': withName(id, lab(loc.board, loc.port))});
});
return JSON.stringify(out);"""),
        [proto("{#IF.NAME}: FEC corrected errors", "rtn.if.pm.fec[{#SNMPINDEX}]", f"{IFPM}.252", vt="FLOAT",
               delay="{$RTN.INTERVAL.PM}", tags=[("component", "radio"), ("if", "{#IF.NAME}")],
               desc="Errors corrected by FEC in the current 15-minute period (pmFecBefCorEr).")],
        delay="{$RTN.INTERVAL.PM}", desc="FEC error counters (not on RTN 380H).")
    return items, [clk, pla, pg, fec]

def model_templates():
    T = "{T}"
    out = []
    for model, extra_desc in (("905", ""), ("910A", ""), ("950A", ""), ("980", "")):
        items, llds = shelf_parts(model)
        if model == "980":
            DPS = f"{HW}.4.30.16.1.1.1"
            llds.append(lld(
                "Control board protection discovery", "rtn.dps.discovery", [("{#DPS.FIRST}", f"{DPS}.2")],
                js("""
var out = [];
rows(value).forEach(function (r) { out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}'], '{#DPS.FIRST}': r['{#DPS.FIRST}']}); });
return JSON.stringify(out);"""),
                [proto("DPS group {#SNMPINDEX}: State", "rtn.dps.state[{#SNMPINDEX}]", f"{DPS}.6", vmap="Huawei RTN DPS state",
                       tags=[("component", "protection")], desc="Control/cross-connect board protection group state (optixDpsState). "
                       "\"Adding\" is commonly reported as the steady state."),
                 proto("DPS group {#SNMPINDEX}: Working board", "rtn.dps.working[{#SNMPINDEX}]", f"{DPS}.2",
                       tags=[("component", "protection")], desc="Slot of the first protection unit (optixDpsFstBid).")],
                delay="{$RTN.INTERVAL.STATUS}", desc="DPS (control board) protection groups, RTN 980 only."))
            extra_desc = " Adds control board (DPS) protection."
        out.append(dict(
            name=f"Huawei OptiX RTN {model} by SNMP", items=items, llds=llds, macros=[], links=[BASE],
            tags=[("class", "network"), ("target", "huawei-rtn")],
            desc=f"Huawei OptiX RTN {model} by SNMP. Links '{BASE}' and adds the subrack items: fan, system clock, "
                 f"PLA groups, IF 1+1 protection and FEC counters.{extra_desc}"))
    # RTN 380H: full-outdoor E-band radio
    LF = f"{HW}.4.40.3.10.4.1"
    items = [
        item("Clock PLL lock state", "rtn.clock.pll", f"{HW}.4.50.35.1.1.1.7.1", vmap="Huawei RTN PLL lock",
             tags=[("component", "clock")], desc="System clock PLL lock state (optixpktSYSclkpllLockstate).",
             triggers=[trig("Clock PLL is unlocked", f"last(/{T}/rtn.clock.pll)=0", "AVERAGE")]),
        item("Clock work mode", "rtn.clock.mode", f"{HW}.4.50.35.1.1.1.8.1", vmap="Huawei RTN clock work mode",
             tags=[("component", "clock")], desc="Packet clock work mode (optixpktSysSynWorkMode): tracing, holdover or free-run.",
             triggers=[trig("Clock is not tracing", f"(count(/{T}/rtn.clock.mode,{{$RTN.CLOCK.PERIOD}},\"eq\",1)=0 and count(/{T}/rtn.clock.mode,{{$RTN.CLOCK.PERIOD}})>0) and {{$RTN.CLOCK.ALERT}}=1",
                            "WARNING", "The packet clock has not been tracing a reference for {$RTN.CLOCK.PERIOD} (holdover or free-run). "
                            "Set {$RTN.CLOCK.ALERT}=0 on a host whose clock runs free by design.")]),
        item("Power mode", "rtn.power.mode", f"{HW}.4.40.7.20.1.0", delay="{$RTN.INTERVAL.INVENTORY}",
             tags=[("component", "power")], desc="NE power mode (optixRtnDevPowerMode)."),
    ]
    far = lld(
        "Radio link identification discovery", "rtn.link.discovery", [("{#LINK.FAR}", f"{LF}.5")] + NAME_COLS,
        js("""
var R = rows(value), lab = labels(R), out = [];
R.forEach(function (r) {
    if (r['{#LINK.FAR}'] === undefined) return;
    var p = String(r['{#SNMPINDEX}']).split('.'), id = 'IF ' + p[1] + '/' + p[p.length - 1];   // index 0.slot.255.port
    out.push({'{#SNMPINDEX}': r['{#SNMPINDEX}'], '{#IF.ID}': id, '{#IF.NAME}': withName(id, lab(p[1], p[p.length - 1]))});
});
return JSON.stringify(out);"""),
        [proto("{#IF.NAME}: Far-end NE ID", "rtn.link.far.neid[{#SNMPINDEX}]", f"{LF}.5", delay="{$RTN.INTERVAL.STATUS}",
               tags=[("component", "radio"), ("if", "{#IF.NAME}")],
               desc="NE ID of the radio at the other end of the link (optixRtnLineFindOutNeid). "
                    "optixRtnLineFindInNeid is the local NE ID.",
               triggers=[trig("{#IF.NAME}: Far-end NE changed", f"change(/{T}/rtn.link.far.neid[{{#SNMPINDEX}}])<>0", "WARNING",
                              "The link now reports a different far-end NE: wrong pointing, a swapped radio or a reconfiguration.",
                              manual=True)])],
        delay="{$RTN.INTERVAL.STATUS}", desc="Link identification: far-end NE ID per IF port (RTN 380H).")
    out.append(dict(name="Huawei OptiX RTN 380H by SNMP", items=items, llds=[far], macros=[], links=[BASE],
                    tags=[("class", "network"), ("target", "huawei-rtn")],
                    desc=f"Huawei OptiX RTN 380H (full-outdoor E-band radio) by SNMP. Links '{BASE}' and adds "
                         "clock PLL state and far-end NE identification."))
    return out

# ----------------------------------------------------------------------------- rendering
def tags_out(tags):
    return [{"tag": t, "value": v} for t, v in tags]

def pre_out(pre):
    return [{"type": t, "parameters": [p]} for t, p in pre]

def trig_out(t, tname, path, proto=False):
    o = {"uuid": uid(*path, "trigger", t["name"]), "expression": t["expr"].replace("{T}", tname),
         "name": t["name"], "priority": t["prio"]}
    if t["desc"]:
        o["description"] = t["desc"]
    if t["manual"]:
        o["manual_close"] = "YES"
    if t["deps"]:
        o["dependencies"] = [{"name": n, "expression": e.replace("{T}", tname)} for n, e in t["deps"]]
    if t["tags"]:
        o["tags"] = tags_out(t["tags"])
    return o

def item_common(it, tname, path):
    o = {"uuid": uid(*path, "item", it["key"]), "name": it["name"]}
    return o

def finish_item(o, it, tname, path, proto=False):
    if it["vt"] != "UNSIGNED":
        o["value_type"] = it["vt"]
    if it["vt"] in ("CHAR", "TEXT"):
        o["trends"] = "0"
    if it["units"]:
        o["units"] = it["units"]
    if it["desc"]:
        o["description"] = it["desc"]
    if it["inventory"] and not proto:
        o["inventory_link"] = it["inventory"]
    if it["vmap"]:
        o["valuemap"] = {"name": it["vmap"]}
    if it["tags"]:
        o["tags"] = tags_out(it["tags"])
    single = [t for t in it["triggers"] if len(set(re.findall(r"/\{T\}/([^,)]+)", t["expr"]))) == 1]
    if single:
        o["trigger_prototypes" if proto else "triggers"] = [trig_out(t, tname, path, proto) for t in single]
    return o

def multi_triggers(objs):
    """Triggers that reference more than one item (rendered at rule/template level)."""
    return [t for it in objs for t in it["triggers"] if len(set(re.findall(r"/\{T\}/([^,)]+)", t["expr"]))) > 1]

def scalar_item(it, tname, path, v7):
    o = item_common(it, tname, path)
    if it["kind"] == "internal":
        o["type"] = "INTERNAL"
    elif it["kind"] == "simple":
        o["type"] = "SIMPLE"
    else:
        o["type"] = "SNMP_AGENT"
        o["snmp_oid"] = it["oid"]
    o["key"] = it["key"]
    if it["delay"] != "1m":
        o["delay"] = it["delay"]
    if it["pre"]:
        o["preprocessing"] = pre_out(it["pre"])
    return finish_item(o, it, tname, path)

def graph_out(g, tname, path):
    """g = (name, [key, or (key, "R") to draw that item on the right Y axis])."""
    name, keys = g
    colors = ["1A7C11", "F63100", "2774A4", "A54F10"]
    out = []
    for i, k in enumerate(keys):
        k, side = (k, "") if isinstance(k, str) else k
        gi = {"color": colors[i], "item": {"host": tname, "key": k}}
        if i:
            gi["sortorder"] = str(i)
        if side == "R":
            gi["yaxisside"] = "RIGHT"
        out.append(gi)
    return {"uuid": uid(*path, "graph", name), "name": name, "graph_items": out}

# Zabbix 6.0 schedules all SNMP items of a bulk-enabled interface that share an interval at the same second
# (the schedule seed is the interface ID). With one shared discovery interval every NE got all its table walks
# at once and about a third answered genError to all of them. So each 6.0 discovery rule gets its own interval:
# 3667 s, 3734 s, ... (steps of 67 s, never a whole minute), which keeps the walks of one NE apart.
LLD_DELAY = {}

def set_lld_delays(templates):
    keys = sorted({L["key"] for t in templates for L in t["llds"]} - {"rtn.alarm.discovery"})
    LLD_DELAY.update({k: str(3600 + 67 * (i + 1)) for i, k in enumerate(keys)})

def lld_out(L, tname, path, v7, items_out):
    """Render one LLD rule. In v7 the alarm rule also appends its walk master item to items_out."""
    # Zabbix 7 runs walk[]/get[] items in asynchronous pollers that send all walks due on an NE at once, and
    # 1-minute table walks per rule overloaded the slower NEs (walks timed out even at 15 s). So v7 polls like
    # v6: discovery[] at the staggered LLD_DELAY and one classic-OID item per value, which the poller can bundle
    # into SNMP bulk requests. Only the small active-alarm table is walked (every minute, for the alarm counters).
    walked = v7 and L["key"] == "rtn.alarm.discovery"
    path = path + ("lld", L["key"])
    rule = {"uuid": uid(*path), "name": L["name"], "key": L["key"]}
    walk_key = L["walk"] or L["key"].replace(".discovery", ".walk")
    pre = []
    if walked:
        cols = []
        for _, c in L["cols"]:
            if c not in cols:
                cols.append(c)
        for p in L["protos"]:
            if p["col"] and p["col"] not in cols:   # calculated prototypes have no column to walk
                cols.append(p["col"])
        for c in L["walk_extra"]:
            if c not in cols:
                cols.append(c)
        existing = [i for i in items_out if i["key"] == walk_key]
        if existing:   # another rule already walks this table: add any missing columns to it
            have = existing[0]["snmp_oid"][5:-1].split(",")
            existing[0]["snmp_oid"] = "walk[" + ",".join(have + [c for c in cols if c not in have]) + "]"
        else:
            items_out.append({"uuid": uid(*path, "walk"), "name": L["name"].replace(" discovery", ": SNMP walk"),
                              "type": "SNMP_AGENT", "snmp_oid": "walk[" + ",".join(cols) + "]", "key": walk_key,
                              "timeout": "{$RTN.SNMP.TIMEOUT}",
                              "delay": L["walk_delay"] or L["delay"], "history": "0", "value_type": "TEXT", "trends": "0",
                              "description": f"Raw SNMP walk feeding '{L['name']}' and its items.",
                              "tags": [{"tag": "component", "value": "raw"}]})
        rule.update({"type": "DEPENDENT", "delay": "0", "master_item": {"key": walk_key}})
        params = []
        for m, c in L["cols"]:
            params += [m, c, "0"]
        pre.append({"type": "SNMP_WALK_TO_JSON", "parameters": params})
    else:
        rule.update({"type": "SNMP_AGENT",
                     "snmp_oid": "discovery[" + ",".join(f"{m},{c}" for m, c in L["cols"]) + "]",
                     "delay": LLD_DELAY[L["key"]] if L["key"] != "rtn.alarm.discovery" else L["delay"]})
    pre.append({"type": "JAVASCRIPT", "parameters": [L["script"]]})
    if walked:
        pre.append({"type": "DISCARD_UNCHANGED_HEARTBEAT", "parameters": ["1h" if L["key"] != "rtn.alarm.discovery" else "10m"]})
    rule["lifetime"] = L["lifetime"]
    if L["desc"]:
        rule["description"] = L["desc"]
    if L["filters"]:
        rule["filter"] = {"evaltype": "AND", "conditions": [
            {"macro": m, "value": v, **({"operator": op} if op != "MATCHES_REGEX" else {}), "formulaid": chr(65 + i)}
            for i, (m, op, v) in enumerate(L["filters"])]}
    protos = []
    for p in L["protos"]:
        o = item_common(p, tname, path)
        oid = f"{p['col']}.{{#SNMPINDEX}}{p['suffix']}"
        if p["kind"] == "calc":
            o.update({"type": "CALCULATED", "key": p["key"], "params": p["formula"]})
            if p["delay"] != "1m":
                o["delay"] = p["delay"]
        elif walked:
            o.update({"type": "DEPENDENT", "key": p["key"], "delay": "0", "master_item": {"key": walk_key}})
            o["preprocessing"] = [{"type": "SNMP_WALK_VALUE", "parameters": [oid, "0"]}] + pre_out(p["pre"])
        else:
            o.update({"type": "SNMP_AGENT", "snmp_oid": oid, "key": p["key"]})
            if p["delay"] != "1m":
                o["delay"] = p["delay"]
            if p["pre"]:
                o["preprocessing"] = pre_out(p["pre"])
        protos.append(finish_item(o, p, tname, path, proto=True))
    rule["preprocessing"] = pre
    rule["item_prototypes"] = protos
    tp = L["trig_protos"] + multi_triggers(L["protos"])
    if tp:
        rule["trigger_prototypes"] = [trig_out(t, tname, path, True) for t in tp]
    if L["graphs"]:
        rule["graph_prototypes"] = [graph_out(g, tname, path) for g in L["graphs"]]
    return rule

def alarm_counters(tname, path):
    """v7 only: counts of active alarms by severity, from the alarm walk."""
    script = """
var sev = {}, eid = {}, ign = new RegExp('{$RTN.ALARM.EID.IGNORE}');
value.split('\\n').forEach(function (l) {
    var m = l.match(/\\.3\\.40\\.30\\.10\\.10\\.1\\.([23])\\.(\\d+) = INTEGER: (\\d+)/);
    if (!m) return;
    (m[1] === '2' ? eid : sev)[m[2]] = m[3];
});
var n = 0;
for (var k in sev) if (sev[k] === '%s' && !ign.test(eid[k] || '')) n++;
return n;"""
    out = []
    for s, label, prio in (("1", "critical", "HIGH"), ("2", "major", "AVERAGE"), ("3", "minor", "WARNING")):
        key = f"rtn.alarm.count[{label}]"
        out.append({"uuid": uid(*path, "item", key), "name": f"Active {label} alarms", "type": "DEPENDENT", "key": key,
                    "delay": "0", "master_item": {"key": "rtn.alarm.walk"},
                    "preprocessing": [{"type": "JAVASCRIPT", "parameters": [(script % s).strip() + "\n"]}],
                    "description": f"Number of active {label} alarms (curAlmDataTable), excluding {{$RTN.ALARM.EID.IGNORE}}.",
                    "tags": [{"tag": "component", "value": "alarm"}]})
    return out

def template_out(t, v7):
    path = (t["name"],)
    items = [scalar_item(i, t["name"], path, v7) for i in t["items"]]
    llds = []
    for L in t["llds"]:
        llds.append(lld_out(L, t["name"], path, v7, items))
    if v7 and t["name"] == BASE:
        items += alarm_counters(t["name"], path)
    o = {"uuid": uid(*path), "template": t["name"], "name": t["name"], "description": t["desc"]}
    if t["links"]:
        o["templates"] = [{"name": n} for n in t["links"]]
    o["groups"] = [{"name": GROUP}]
    o["items"] = items
    o["discovery_rules"] = llds
    o["tags"] = tags_out(t["tags"])
    if t["macros"]:
        o["macros"] = [{"macro": m, "value": v, "description": d} for m, v, d in t["macros"]]
    used = set()
    def walk(x):
        if isinstance(x, dict):
            if "valuemap" in x:
                used.add(x["valuemap"]["name"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(o)
    if t.get("graphs"):
        o["graphs"] = [graph_out(g, t["name"], path) for g in t["graphs"]]
    if used:
        o["valuemaps"] = [{"uuid": uid(*path, "valuemap", n), "name": n,
                           "mappings": [{"value": str(k), "newvalue": v} for k, v in sorted(VALUEMAPS[n].items())]}
                          for n in sorted(used)]
    return o

class Dumper(yaml.SafeDumper):
    pass
def str_rep(d, s):
    if "\n" in s:
        return d.represent_scalar("tag:yaml.org,2002:str", s, style="|")
    return d.represent_scalar("tag:yaml.org,2002:str", s)
Dumper.add_representer(str, str_rep)

def export(templates, v7):
    doc = {"zabbix_export": {"version": "7.0" if v7 else "6.0"}}
    doc["zabbix_export"]["template_groups" if v7 else "groups"] = [{"uuid": uid("group", GROUP), "name": GROUP}]
    doc["zabbix_export"]["templates"] = [template_out(t, v7) for t in templates]
    # graphs of template items (not prototypes) are listed after the templates, not inside them
    graphs = [g for t in doc["zabbix_export"]["templates"] for g in t.pop("graphs", [])]
    if graphs:
        doc["zabbix_export"]["graphs"] = graphs
    return yaml.dump(doc, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=1000)

def slug(name):
    return name.lower().replace("huawei optix ", "huawei_").replace(" by snmp", "_snmp").replace(" ", "_")

if __name__ == "__main__":
    base = base_template()
    models = model_templates()
    set_lld_delays([base] + models)
    for v7, ver in ((False, "6.0"), (True, "7.0")):
        out = os.path.join(OUT_DIR, ver)
        os.makedirs(out, exist_ok=True)
        path = os.path.join(out, OUT_NAME)
        open(path, "w").write(export([base] + models, v7))
        print(os.path.relpath(path, ROOT))

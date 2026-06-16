"""
Waveshare "Modbus POE ETH Relay" operational control panel.

Serves a self-contained web page that switches the 8 relay channels on the
board at RELAY_HOST. The board bridges Ethernet straight to its internal
Modbus engine, so it speaks *Modbus-RTU framing (with CRC) over a raw TCP
socket on port 502* -- NOT standard Modbus-TCP (MBAP header). This script
talks that dialect directly, so it needs no third-party libraries.

Run:
    python relay_control.py
then open http://127.0.0.1:8080/ in a browser.

Requires: Python 3.8+ standard library only.
"""

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RELAY_HOST   = "172.30.0.200"   # board IP (confirmed reachable)
RELAY_PORT   = 502              # Modbus/TCP socket
UNIT_ID      = 0x01             # board's Modbus address (read from reg 0x4000)
NUM_CHANNELS = 8
SOCK_TIMEOUT = 4.0              # seconds per Modbus transaction

WEB_HOST = "127.0.0.1"          # this PC only; set to "0.0.0.0" to expose on the LAN
WEB_PORT = 8088

# Friendly labels for each channel (edit to match your wiring).
CHANNEL_LABELS = {
    1: "Relay 1",
    2: "Relay 2",
    3: "Relay 3",
    4: "Relay 4",
    5: "Relay 5",
    6: "Relay 6",
    7: "Relay 7",
    8: "Relay 8",
}

# Coil values understood by the board (FC05 "Write Single Coil").
COIL_ON     = 0xFF00
COIL_OFF    = 0x0000
COIL_TOGGLE = 0x5500
ADDR_ALL    = 0x00FF   # special coil address that targets every channel at once

# ---------------------------------------------------------------------------
# Modbus-RTU-over-TCP client
# ---------------------------------------------------------------------------
_modbus_lock = threading.Lock()   # board allows one transaction at a time


def _crc16(data: bytes) -> bytes:
    """Modbus CRC16 (little-endian, appended lo byte first)."""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def _transaction(payload: bytes, retries: int = 1) -> bytes:
    """Send one RTU frame (payload + CRC) and return the full reply frame."""
    frame = payload + _crc16(payload)
    last_err = None
    with _modbus_lock:
        for _ in range(retries + 1):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(SOCK_TIMEOUT)
            try:
                s.connect((RELAY_HOST, RELAY_PORT))
                s.sendall(frame)
                reply = s.recv(256)
                if not reply:
                    raise IOError("empty reply")
                if reply[1] & 0x80:        # Modbus exception bit
                    raise IOError("modbus exception code 0x%02X" % reply[2])
                return reply
            except Exception as e:        # noqa: BLE001 - reported to caller
                last_err = e
                time.sleep(0.15)
            finally:
                s.close()
    raise IOError("relay transaction failed: %s" % last_err)


def read_status() -> list:
    """Return a list of NUM_CHANNELS booleans (True == energised)."""
    payload = bytes([UNIT_ID, 0x01, 0x00, 0x00, 0x00, NUM_CHANNELS])
    reply = _transaction(payload)
    byte_count = reply[2]
    data = reply[3:3 + byte_count]
    states = []
    for ch in range(NUM_CHANNELS):
        states.append(bool(data[ch // 8] & (1 << (ch % 8))))
    return states


def _write_coil(addr: int, value: int) -> None:
    payload = bytes([UNIT_ID, 0x05,
                     (addr >> 8) & 0xFF, addr & 0xFF,
                     (value >> 8) & 0xFF, value & 0xFF])
    _transaction(payload)


def set_channel(ch: int, on: bool) -> None:
    _write_coil(ch - 1, COIL_ON if on else COIL_OFF)


def toggle_channel(ch: int) -> None:
    _write_coil(ch - 1, COIL_TOGGLE)


def set_all(on: bool) -> None:
    _write_coil(ADDR_ALL, COIL_ON if on else COIL_OFF)


def toggle_all() -> None:
    _write_coil(ADDR_ALL, COIL_TOGGLE)


def pulse_channel(ch: int, seconds: float) -> None:
    """Energise a channel, then de-energise it after `seconds` (momentary)."""
    set_channel(ch, True)

    def _off():
        time.sleep(max(0.1, min(seconds, 3600)))
        try:
            set_channel(ch, False)
        except Exception:
            pass

    threading.Thread(target=_off, daemon=True).start()


# ---------------------------------------------------------------------------
# Web layer
# ---------------------------------------------------------------------------
PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relay Control &mdash; Modbus POE ETH</title>
<style>
  :root { --grn:#7bae23; --grn-d:#5d8519; --bg:#15171c; --card:#1f232b;
          --line:#2c313c; --txt:#e8ebef; --dim:#8b94a3; --red:#d9534f; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:'Segoe UI',system-ui,sans-serif; background:var(--bg);
         color:var(--txt); }
  header { padding:18px 22px; border-bottom:1px solid var(--line);
           display:flex; align-items:center; gap:12px; }
  header h1 { font-size:18px; margin:0; font-weight:600; }
  header .ip { color:var(--dim); font-size:13px; margin-left:auto; }
  #conn { width:10px; height:10px; border-radius:50%; background:var(--dim); }
  #conn.ok { background:var(--grn); } #conn.bad { background:var(--red); }
  .bar { display:flex; gap:10px; padding:16px 22px; flex-wrap:wrap;
         border-bottom:1px solid var(--line); }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr));
          gap:14px; padding:22px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px;
          padding:16px; }
  .card .top { display:flex; align-items:center; justify-content:space-between; }
  .card .lbl { font-weight:600; font-size:15px; }
  .card .num { color:var(--dim); font-size:12px; }
  .state { font-size:12px; font-weight:600; letter-spacing:.5px; margin:10px 0 14px; }
  .state.on  { color:var(--grn); } .state.off { color:var(--dim); }
  .row { display:flex; gap:8px; }
  button { flex:1; cursor:pointer; border:1px solid var(--line); background:#262b34;
           color:var(--txt); padding:9px 10px; border-radius:8px; font-size:13px;
           font-weight:600; transition:.12s; }
  button:hover { border-color:var(--grn); }
  button:active { transform:translateY(1px); }
  button.on  { background:var(--grn); border-color:var(--grn); color:#0e1206; }
  button.off { background:#2e333d; }
  button.ghost { background:transparent; }
  .pulse { margin-top:8px; align-items:center; }
  .dur { width:64px; background:#262b34; color:var(--txt); border:1px solid var(--line);
         border-radius:8px; padding:8px; font-size:13px; text-align:right; }
  .dur:focus { outline:none; border-color:var(--grn); }
  .unit { color:var(--dim); font-size:13px; margin:0 4px 0 -2px; }
  .switch { width:46px; height:26px; border-radius:13px; background:#3a404b;
            position:relative; cursor:pointer; transition:.15s; flex:none; }
  .switch.on { background:var(--grn); }
  .switch::after { content:""; position:absolute; top:3px; left:3px; width:20px;
            height:20px; border-radius:50%; background:#fff; transition:.15s; }
  .switch.on::after { left:23px; }
  .bar button { flex:none; padding:9px 16px; }
  #msg { padding:0 22px 16px; color:var(--red); font-size:13px; min-height:18px; }
</style>
</head>
<body>
<header>
  <span id="conn"></span>
  <h1>Modbus POE ETH Relay</h1>
  <span class="ip">__HOST__ &middot; unit __UNIT__</span>
</header>
<div class="bar">
  <button class="on"  data-act="all_on">All ON</button>
  <button class="off" data-act="all_off">All OFF</button>
  <button class="ghost" data-act="all_toggle">Toggle all</button>
  <button class="ghost" data-act="refresh">Refresh</button>
</div>
<div id="msg"></div>
<div class="grid" id="grid">__CARDS__</div>
<script>
const N = __N__;
let busy = false;

function setConn(ok){ document.getElementById('conn').className = ok ? 'ok' : 'bad'; }
function msg(t){ document.getElementById('msg').textContent = t || ''; }

async function api(body){
  busy = true;
  try {
    const r = await fetch('/api/control', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const j = await r.json();
    if(!j.ok){ msg(j.error||'error'); setConn(false); }
    else { msg(''); render(j.channels); setConn(true); }
  } catch(e){ msg('connection lost'); setConn(false); }
  finally { busy = false; }
}

async function refresh(){
  if(busy) return;
  try {
    const r = await fetch('/api/status');
    const j = await r.json();
    if(j.ok){ render(j.channels); setConn(true); }
    else setConn(false);
  } catch(e){ setConn(false); }
}

// One delegated handler for every control (cards are rendered server-side).
document.addEventListener('click', function(e){
  const t = e.target.closest('[data-act]');
  if(!t) return;
  const act = t.dataset.act;
  if(act === 'refresh'){ refresh(); return; }
  const ch = t.dataset.ch ? parseInt(t.dataset.ch, 10) : 0;
  if(act === 'pulse'){
    const d = document.getElementById('pl'+ch);
    const secs = d ? (parseFloat(d.value) || 1) : 1;
    api({action:'pulse', channel:ch, seconds:secs});
    return;
  }
  api({action: act, channel: ch});
});

function render(states){
  for(let i=1;i<=N;i++){
    const on = !!states[i-1];
    document.getElementById('sw'+i).className = 'switch'+(on?' on':'');
    const st = document.getElementById('st'+i);
    st.textContent = on?'ON':'OFF'; st.className = 'state '+(on?'on':'off');
    document.getElementById('on'+i).className = on?'on':'';
    document.getElementById('off'+i).className = on?'':'off';
  }
}

refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>"""


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _cards() -> str:
    """Render the channel cards server-side (no fragile inline-onclick JS)."""
    cards = []
    for i in range(1, NUM_CHANNELS + 1):
        label = _esc(CHANNEL_LABELS.get(i, "Relay %d" % i))
        cards.append(
            '<div class="card" id="c{i}">'
            '<div class="top"><span class="lbl">{label}</span>'
            '<div class="switch" id="sw{i}" data-ch="{i}" data-act="toggle"></div></div>'
            '<div class="num">Channel {i}</div>'
            '<div class="state off" id="st{i}">OFF</div>'
            '<div class="row">'
            '<button id="on{i}" data-ch="{i}" data-act="on">ON</button>'
            '<button id="off{i}" data-ch="{i}" data-act="off">OFF</button>'
            '<button class="ghost" data-ch="{i}" data-act="toggle">&#8645;</button>'
            '</div>'
            '<div class="row pulse">'
            '<input type="number" id="pl{i}" class="dur" value="1" min="0.1" step="0.1">'
            '<span class="unit">s</span>'
            '<button class="ghost" data-ch="{i}" data-act="pulse">Pulse</button>'
            '</div></div>'.format(i=i, label=label)
        )
    return "".join(cards)


def _page() -> bytes:
    page = (PAGE
            .replace("__HOST__", RELAY_HOST)
            .replace("__UNIT__", str(UNIT_ID))
            .replace("__N__", str(NUM_CHANNELS))
            .replace("__CARDS__", _cards()))
    return page.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):    # quiet console
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = _page()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/api/status"):
            try:
                self._json({"ok": True, "channels": read_status()})
            except Exception as e:    # noqa: BLE001
                self._json({"ok": False, "error": str(e)}, 200)
        else:
            self._json({"ok": False, "error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/api/control":
            self._json({"ok": False, "error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length) or b"{}")
            action = req.get("action")
            ch = int(req.get("channel", 0) or 0)

            if action == "on":            set_channel(ch, True)
            elif action == "off":         set_channel(ch, False)
            elif action == "toggle":      toggle_channel(ch)
            elif action == "all_on":      set_all(True)
            elif action == "all_off":     set_all(False)
            elif action == "all_toggle":  toggle_all()
            elif action == "pulse":       pulse_channel(ch, float(req.get("seconds", 1)))
            else:
                self._json({"ok": False, "error": "unknown action"}, 200)
                return

            time.sleep(0.05)              # let the board settle before reading back
            self._json({"ok": True, "channels": read_status()})
        except Exception as e:            # noqa: BLE001
            self._json({"ok": False, "error": str(e)}, 200)


def main():
    print("Relay control panel")
    print("  board : %s:%d  (unit %d, %d channels)"
          % (RELAY_HOST, RELAY_PORT, UNIT_ID, NUM_CHANNELS))
    try:
        print("  status:", read_status())
    except Exception as e:
        print("  status: UNREACHABLE -", e)
    url_host = "127.0.0.1" if WEB_HOST in ("0.0.0.0", "") else WEB_HOST
    print("  web   : http://%s:%d/" % (url_host, WEB_PORT))
    print("Ctrl-C to stop.")
    srv = ThreadingHTTPServer((WEB_HOST, WEB_PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
        srv.shutdown()


if __name__ == "__main__":
    main()

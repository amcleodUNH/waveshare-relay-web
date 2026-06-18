# waveshare-relay-web

A zero-dependency web control panel for the Waveshare **Modbus POE ETH Relay**
(8-channel) board. Run one Python file, open a browser, and switch relays.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

![Relay control panel](docs/relay-panel.png)

## Why

The Waveshare *Modbus POE ETH Relay* bridges Ethernet straight to its internal
Modbus engine. Despite listening on TCP port 502, it does **not** speak standard
Modbus-TCP (MBAP header) — it expects raw **Modbus-RTU frames with a CRC over the
socket**. Standard Modbus-TCP clients silently time out against it. This project
talks that RTU-over-TCP dialect directly, using only the Python standard library,
and wraps it in a clean web UI.

## Features

- Per-channel **ON / OFF / Toggle**, with a live toggle switch
- **All ON / All OFF / Toggle all**
- **Momentary pulse** per channel — energise for N seconds, then auto-release
- Live status polling every 2 s with a connection indicator
- Editable channel labels to match your wiring
- No third-party dependencies — Python 3.8+ standard library only

## Quick start

```bash
python relay_control.py
```

Then open <http://127.0.0.1:8088/>.

The console prints the board's current relay states on startup so you can confirm
connectivity before opening the page.

## Configuration

Edit the constants at the top of [`relay_control.py`](relay_control.py):

| Setting | Default | Meaning |
|---|---|---|
| `RELAY_HOST` | `172.30.0.200` | IP address of the relay board |
| `RELAY_PORT` | `502` | Modbus/TCP socket port |
| `UNIT_ID` | `0x01` | Board's Modbus address (read from register `0x4000`) |
| `NUM_CHANNELS` | `8` | Number of relay channels |
| `WEB_HOST` | `127.0.0.1` | Web bind address (this PC only); set to `0.0.0.0` to expose on the LAN |
| `WEB_PORT` | `8088` | Web server port |
| `CHANNEL_LABELS` | `Relay 1..8` | Friendly name per channel |

> **Security note:** the panel itself has no authentication. It binds to
> `127.0.0.1` (this PC only) by default. If you set `WEB_HOST = "0.0.0.0"` to
> reach it from other machines, anyone on your LAN can switch the relays — put
> it behind a trusted network / reverse proxy with auth if that matters for your
> deployment.

## HTTP API

The page is driven by a small JSON API you can also call directly:

| Method | Path | Body | Result |
|---|---|---|---|
| `GET` | `/api/status` | — | `{ "ok": true, "channels": [bool x N] }` |
| `POST` | `/api/control` | `{"action":"on","channel":1}` | sets channel 1 ON |
| `POST` | `/api/control` | `{"action":"off","channel":1}` | sets channel 1 OFF |
| `POST` | `/api/control` | `{"action":"toggle","channel":1}` | toggles channel 1 |
| `POST` | `/api/control` | `{"action":"all_on"}` | all channels ON |
| `POST` | `/api/control` | `{"action":"all_off"}` | all channels OFF |
| `POST` | `/api/control` | `{"action":"all_toggle"}` | toggles all channels |
| `POST` | `/api/control` | `{"action":"pulse","channel":1,"seconds":1.5}` | pulse channel 1 |

Every control response also returns the fresh `channels` array.

Example:

```bash
curl -X POST http://127.0.0.1:8088/api/control \
  -H "Content-Type: application/json" \
  -d '{"action":"pulse","channel":1,"seconds":2}'
```

## Protocol notes

The board is controlled with standard Modbus function codes wrapped in RTU framing
(`address, function, data..., CRC16`) sent over a TCP socket:

- **Read relay status** — FC `0x01` (Read Coils), 8 coils from `0x0000`
- **Set one relay** — FC `0x05` (Write Single Coil): `0xFF00` = ON, `0x0000` = OFF,
  `0x5500` = toggle, at coil address `channel - 1`
- **Set all relays** — FC `0x05` to the special coil address `0x00FF`

All traffic goes over a **single persistent TCP connection**, guarded by a lock so
only one transaction is in flight at a time. Replies are framed by reading exactly
the number of bytes each function code implies, so the reused stream never desyncs.
If the link drops, the next transaction transparently reconnects and retries once.
This deliberately avoids opening a new socket per command — these boards have a very
small connection pool, and rapid connect/close churn can exhaust it and wedge the
device (requiring a power-cycle).

## Compatibility

Built and verified against the Waveshare **Modbus POE ETH Relay** (8-channel).
Other Waveshare RTU-over-TCP relay boards should work by adjusting `NUM_CHANNELS`
and `UNIT_ID`.

## License

[MIT](LICENSE)

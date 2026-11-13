"""A LifeSmart hub, simulated at the datagram level (R40).

The integration's real `LifeSmartAPI` is used unchanged except for where the
socket would be opened: `async_start` installs a transport that hands each
datagram to this hub instead of the network. So message building, signing,
the resend rules, reply matching and NOTIFY parsing all run for real.

What the hub does is taken from the spec and from what was measured on the
user's two hubs (Smart Station `LSJZX1K` and DEFED `LSDEFED`, firmware
1.0.94p10):

* It checks the signature with its own token (LI §3.2.1) and the timestamp
  against its clock. Either one wrong: `{"code": 101, "msg": {"ts": ...}}`
  (PROGRESS R31 / R34). It does not check the model (R34).
* GET is answered with packet type 2, SET with 4 (LI §3.1). NOTIFY is 9.
* Switching a channel is followed by a NOTIFY carrying the new value.

Shapes the spec does not show (the `add` / `del` NOTIFY, D6) follow what
api.py reads; they are not evidence of what a real hub sends.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import struct
import time
from typing import Any, Callable

from custom_components.lifesmart.api import LifeSmartAPI, _LifeSmartDatagramProtocol

HOST = "192.168.1.50"
LOCAL_IP = "192.168.1.10"
MODEL = "OD_TEST_MODEL"
TOKEN = "0123456789abcdefABCD"
BOUND_PORT = 50001
TIMEOUT = 0.05  # seconds, see the `sim` fixture
AGT = "A3EAAABtAEwQRzM0NzA2NQ"

GET, GET_REPLY, SET, SET_REPLY, NOTIFY = 1, 2, 3, 4, 9


def _device(me: str, devtype: str, name: str, data: dict, **extra: Any) -> dict:
    return {"me": me, "agt": AGT, "devtype": devtype, "name": name, "stat": 1,
            "epver": "1.2.3", "data": data, **extra}


def default_devices() -> list[dict]:
    """One of each kind the integration handles. The first three have the
    shapes seen on the user's hubs (R29); the rest the spec's."""
    return [
        # Seen on the user's hubs: a three-gang switch with a battery, a
        # switch with I1-I3 channels the spec does not describe, and V_SI.
        _device("2711", "SL_SW_ND3", "Stairs", {
            "L1": {"v": 1, "name": "Stairs main", "valts": 0},
            "L2": {"v": 0, "name": "{$EPN} Side", "valts": 0},
            "L3": {"v": 0, "name": "", "valts": 0},
            "V": {"v": 90, "valts": 0},
        }, lDbm=-61),
        _device("2712", "SL_SW_RC", "Living room", {
            "L1": {"v": 0, "name": "Front", "valts": 0},
            "I1": {"type": 30, "val": 0, "valts": 0},
        }, lDbm=-70),
        _device("0020", "V_SI", "System", {"TR": {"v": 1}}),
        # The spec's shapes, for the platforms the user's hubs do not have.
        _device("2713", "SL_NATURE", "Nature", {
            "L1": {"v": 0, "name": "Panel"}, "T": {"v": 245},
        }, lDbm=-55),
        _device("2714", "SL_P", "Curtain", {
            "P1": {"type": 128, "v": 0}, "P8": {"v": 80},
        }),
        _device("2715", "SL_P_IR", "TV remote", {}),
        _device("2716", "SL_SC_BB_V2", "Clicker", {"BN": {"v": 0}, "V": {"v": 77}}, lDbm=-80),
        _device("2717", "SL_MC_ND1", "Accessory", {
            "L1": {"v": 0, "name": "Lamp"}, "B1": {"v": 0}, "V": {"v": 50},
        }, lDbm=-66),
    ]


def default_scenes() -> list[dict]:
    return [
        {"id": "AI_SCENE_000001", "name": "Movie night", "cls": "scene"},
        {"id": "AI_GROUP_000002", "name": "All lamps", "cls": "groupsw"},
        {"id": "AI_GROUP_000003", "name": "Bulbs", "cls": "grouphw"},
        {"id": "AI_GROUP_000004", "name": "Not shown", "cls": "something_else"},
    ]


def spec_signature(obj: str, args: dict, ts: int, model: str, token: str) -> str:
    """LI §3.2.1, written here independently of api.py: `obj`, the args
    sorted by name, `ts`, `model`, `token`, comma separated, MD5. Values as
    the hub reads them from JSON (true / false); arrays and objects are not
    signed."""
    parts = [f"obj:{obj}"]
    for key in sorted(args):
        value = args[key]
        if isinstance(value, (list, dict)):
            continue
        if isinstance(value, bool):
            value = "true" if value else "false"
        parts.append(f"{key}:{value}")
    parts += [f"ts:{ts}", f"model:{model}", f"token:{token}"]
    return hashlib.md5(",".join(parts).encode()).hexdigest()


def datagram(pkg_type: int, body: dict) -> bytes:
    raw = json.dumps(body).encode()
    return struct.pack(">2sHHI", b"JL", 0, pkg_type, len(raw)) + raw


class Hub:
    """State and behaviour of one simulated hub."""

    def __init__(self) -> None:
        self.token = TOKEN
        self.clock_ahead = 0
        self.devices: list[dict] = default_devices()
        self.scenes: list[dict] = default_scenes()
        self.remotes = [{"id": "AI_IR_2715_1", "name": "TV", "category": "tv", "brand": "x"}]
        self.remote_keys = {"AI_IR_2715_1": {"power": "k1", "vol_up": "k2"}}
        self.version = {"ver": "1.0.94p10", "osver": "4.4.94", "mgatype": "LSJZX1K"}
        self.timezone = {"timezone": 8, "summer": False}
        # Everything the hub received, as (obj, args, pkg_type).
        self.received: list[tuple[str, dict, int]] = []
        # obj (or "obj:cfg") -> list of replies to use instead of the normal
        # answer; an exception is raised as "no reply" (a timeout).
        self.overrides: dict[str, list[Any]] = {}
        # True: no reply at all, to anything.
        self.silent = False
        # obj (or "obj:cfg") -> exception the socket raises when sending it.
        self.send_errors: dict[str, BaseException] = {}
        # Send the NOTIFY that follows a switch command.
        self.push_after_set = True
        self.apis: list[SimulatedAPI] = []
        self.next_notify_id = 9000

    # --- the device list as a dict, for edits in tests ---------------------
    def device(self, me: str) -> dict:
        return next(d for d in self.devices if d["me"] == me)

    def sent(self, obj: str, **match: Any) -> list[dict]:
        """Args of every request for `obj` whose args include `match`."""
        return [
            args for o, args, _ in self.received
            if o == obj and all(args.get(k) == v for k, v in match.items())
        ]

    # --- answering ------------------------------------------------------------
    def handle(self, api: "SimulatedAPI", data: bytes) -> bytes | None:
        _remark, _, pkg_type, size = struct.unpack(">2sHHI", data[:10])
        request = json.loads(data[10:10 + size])
        obj, args, sys_ = request["obj"], request["args"], request["sys"]
        self.received.append((obj, args, pkg_type))
        for key in (f"{obj}:{args.get('cfg') or args.get('cmd') or ''}", obj):
            if key in self.send_errors:
                raise self.send_errors[key]
        if self.silent:
            return None
        reply_type = GET_REPLY if pkg_type == GET else SET_REPLY

        hub_time = int(time.time()) + self.clock_ahead
        expected = spec_signature(obj, args, sys_["ts"], sys_["model"], self.token)
        if sys_["sign"] != expected or abs(sys_["ts"] - hub_time) > 300:
            return datagram(reply_type, {"id": request["id"], "code": 101, "msg": {"ts": hub_time}})

        for key in (f"{obj}:{args.get('cfg') or args.get('cmd') or ''}", obj):
            queue = self.overrides.get(key)
            if queue:
                reply = queue.pop(0)
                if isinstance(reply, BaseException):
                    return None
                body = {"id": request["id"], **reply}
                return datagram(reply_type, body)

        body = {"id": request["id"], **self.answer(api, obj, args, pkg_type)}
        return datagram(reply_type, body)

    def answer(self, api: "SimulatedAPI", obj: str, args: dict, pkg_type: int) -> dict:
        ok: dict = {"code": 0, "msg": {}}
        if obj == "eps":
            return {"code": 0, "msg": copy.deepcopy(self.devices)}
        if obj == "ep" and pkg_type == GET:
            return {"code": 0, "msg": copy.deepcopy(self.device(args["me"]))}
        if obj == "ep" and pkg_type == SET:
            channel = self.device(args["me"])["data"].setdefault(args["idx"], {})
            channel["v"] = args["val"]
            if self.push_after_set:
                # After the reply, which goes out with call_soon.
                api.loop.call_later(0.001, self.push, api, {"chg": [
                    {"me": args["me"], args["idx"]: {"v": args["val"]}}
                ]})
            return ok
        if obj == "scene":
            return {"code": 0, "msg": copy.deepcopy(self.scenes)}
        if obj == "doscene":
            return ok
        if obj == "spotremote":
            if args["cmd"] == "getlist":
                return {"code": 0, "msg": copy.deepcopy(self.remotes)}
            if args["cmd"] == "getkeys":
                return {"code": 0, "msg": copy.deepcopy(self.remote_keys.get(args["id"], {}))}
            return ok
        if obj == "config":
            cfg = args["cfg"]
            if cfg == "getver":
                return {"code": 0, "msg": dict(self.version)}
            if cfg == "timezone":
                if "timezone" in args:
                    self.timezone = {"timezone": args["timezone"], "summer": args["summer"]}
                    return ok
                return {"code": 0, "msg": dict(self.timezone)}
            if cfg == "devname" and "me" in args:
                self.device(args["me"])["name"] = args["name"]
            return ok
        return {"code": 10004, "msg": f"unknown obj {obj}"}

    # --- pushing --------------------------------------------------------------
    def push(self, api: "SimulatedAPI | None" = None, body: dict | None = None) -> None:
        """Send a NOTIFY (LI §4) to one API, or to every API of this hub."""
        self.next_notify_id += 1
        packet = datagram(NOTIFY, {"id": self.next_notify_id, **(body or {})})
        for target in [api] if api else list(self.apis):
            if target._protocol is not None:
                target._protocol.datagram_received(packet, (HOST, 12348))


class FakeTransport:
    """Stands in for the UDP socket of one API."""

    def __init__(self, hub: Hub, api: "SimulatedAPI") -> None:
        self._hub = hub
        self._api = api
        self.closed = False

    def sendto(self, data: bytes, addr: Any = None) -> None:
        reply = self._hub.handle(self._api, data)
        if reply is not None:
            self._api.loop.call_soon(self._deliver, reply)

    def _deliver(self, reply: bytes) -> None:
        if not self.closed and self._api._protocol is not None:
            self._api._protocol.datagram_received(reply, (HOST, 12348))

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        return ("0.0.0.0", BOUND_PORT) if name == "sockname" else default

    def close(self) -> None:
        self.closed = True


class SimulatedAPI(LifeSmartAPI):
    """LifeSmartAPI with the socket replaced by a `Hub`. Nothing else differs."""

    hub: Hub

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.loop = asyncio.get_running_loop()
        self.hub.apis.append(self)

    async def async_start(self) -> None:
        if self._transport is not None:
            return
        self._protocol = _LifeSmartDatagramProtocol(self)
        self._transport = FakeTransport(self.hub, self)  # type: ignore[assignment]
        if self.local_port == 0:
            self.local_port = BOUND_PORT


def api_class_for(hub: Hub) -> Callable[..., SimulatedAPI]:
    return type("SimulatedAPIForTest", (SimulatedAPI,), {"hub": hub})

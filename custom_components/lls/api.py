"""LifeSmart API implementation."""
import asyncio
import json
import time
import hashlib
import struct
import logging
from collections.abc import Callable
from typing import Any, Dict, Optional, Tuple
from .const import API_PORT, REMARK, CMD_NOTIFY, CMD_REPORT, CMD_SET

_LOGGER = logging.getLogger(__name__)

class LifeSmartAPI:
    def __init__(self, host: str, model: str, token: str, timeout: int = 5, local_port: int = 12346):
        self.host = host
        self.model = model
        self.token = token
        self.sequence = 1
        self.timeout = timeout
        self.local_port = local_port
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._protocol: Optional["_LifeSmartDatagramProtocol"] = None
        self._pending: Dict[int, asyncio.Future] = {}
        self._report_listeners: set[Callable[[Dict[str, Any]], None]] = set()
        self._state_listeners: Dict[Tuple[str, str], set[Callable[[Any], None]]] = {}
        self.ts_offset: int = 0

    def _create_signature(self, obj: str, args: Dict[str, Any], ts: int) -> str:
        sortable_items = []
        for k, v in args.items():
            if isinstance(v, (list, tuple)):
                continue
            sortable_items.append((k, v))
        sorted_args = sorted(sortable_items)
        parts = [f"obj:{obj}"]
        for k, v in sorted_args:
            parts.append(f"{k}:{v}")
        parts.append(f"ts:{ts}")
        parts.append(f"model:{self.model}")
        parts.append(f"token:{self.token}")
        base_string = ",".join(parts)
        return hashlib.md5(base_string.encode()).hexdigest()

    def apply_ts_from_response(self, response: Dict[str, Any]) -> None:
        """Calculate ts_offset from a code-101 hub response."""
        hub_ts = response.get("msg", {}).get("ts") if isinstance(response.get("msg"), dict) else None
        if isinstance(hub_ts, int):
            self.ts_offset = hub_ts - int(time.time())
            _LOGGER.debug("ts_offset set to %d seconds", self.ts_offset)

    def _create_message(self, obj: str, args: Dict[str, Any], pkg_type: int, msg_id: int) -> bytes:
        ts = int(time.time()) + self.ts_offset
        sign = self._create_signature(obj, args, ts)

        body = {
            "sys": {
                "ver": 1,
                "sign": sign,
                "model": self.model,
                "ts": ts
            },
            "id": msg_id,
            "obj": obj,
            "args": args
        }

        body_json = json.dumps(body).encode('utf-8')
        header = struct.pack('>2sHHI', 
                           REMARK.encode(),
                           0,
                           pkg_type,
                           len(body_json))

        return header + body_json

    async def async_start(self) -> None:
        if self._transport is not None:
            return
        loop = asyncio.get_running_loop()
        protocol = _LifeSmartDatagramProtocol(self)
        transport, _ = await loop.create_datagram_endpoint(
            lambda: protocol,
            local_addr=("0.0.0.0", self.local_port),
        )
        self._transport = transport
        self._protocol = protocol
        if self.local_port == 0:
            sockname = transport.get_extra_info("sockname")
            if isinstance(sockname, tuple) and len(sockname) >= 2:
                self.local_port = int(sockname[1])

    async def async_stop(self) -> None:
        if self._transport is None:
            return
        transport = self._transport
        self._transport = None
        self._protocol = None
        try:
            transport.close()
        finally:
            for fut in list(self._pending.values()):
                if not fut.done():
                    fut.cancel()
            self._pending.clear()

    def register_report_listener(self, listener: Callable[[Dict[str, Any]], None]) -> Callable[[], None]:
        self._report_listeners.add(listener)
        def _unsub() -> None:
            self._report_listeners.discard(listener)
        return _unsub

    def register_state_listener(self, me: str, idx: str, listener: Callable[[Any], None]) -> Callable[[], None]:
        key = (me, idx)
        listeners = self._state_listeners.setdefault(key, set())
        listeners.add(listener)
        def _unsub() -> None:
            bucket = self._state_listeners.get(key)
            if not bucket:
                return
            bucket.discard(listener)
            if not bucket:
                self._state_listeners.pop(key, None)
        return _unsub

    async def send_command(self, obj: str, args: Dict[str, Any], pkg_type: int, timeout: Optional[float] = None) -> Dict[str, Any]:
        await self.async_start()
        if self._transport is None:
            raise RuntimeError("UDP transport not started")

        msg_id = self.sequence
        self.sequence += 1
        message = self._create_message(obj, args, pkg_type, msg_id)

        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending[msg_id] = fut
        try:
            self._transport.sendto(message, (self.host, API_PORT))
            response = await asyncio.wait_for(fut, timeout=timeout or self.timeout)
            return response
        finally:
            self._pending.pop(msg_id, None)

    async def discover_devices(self):
        # 移除錯誤的 hardcode ID，改為標準空請求
        args = {}
        # args = {"me": "2d02"}
        return await self.send_command("eps", args, 1)

    async def get_remote_list(self) -> list:
        """Retrieve IR remote list for devices."""
        args = {
            "cmd": "getlist"
        }
        response = await self.send_command("spotremote", args, 3)
        
        if response and response.get("code") == 0 and "msg" in response:
            remote_list = response["msg"]
            all_keys = []

            for remote in remote_list:
                if "id" in remote:
                    keys = await self.get_remote_keys(remote["id"])
                    if keys and keys.get("code") == 0 and "msg" in keys:
                        all_keys.append({"remote": remote, "keys": keys["msg"]})
            return all_keys
        return []

    async def configure_event_service(self, host: str, port: int) -> Dict[str, Any]:
        args = {"cfg": "notify", "host": host, "port": port}
        return await self.send_command("config", args, CMD_SET)

    async def get_remote_keys(self, remote_id: str) -> Dict[str, Any]:
        """Retrieve IR remote keys for a specific device."""
        args = {
            "id": remote_id,
            "cmd": "getkeys"
        }
        return await self.send_command("spotremote", args, 3)

    async def send_remote_key(self, remote_id: str, key: str) -> Dict[str, Any]:
        """Send IR remote key command."""
        args = {
            "id": remote_id,
            "cmd": "sendkey",
            "key": key
        }
        return await self.send_command("spotremote", args, 3)

    def _handle_datagram(self, data: bytes) -> None:
        if len(data) < 10:
            return
        try:
            remark, _, pkg_type, pkg_size = struct.unpack(">2sHHI", data[:10])
            if remark.decode(errors="ignore") != REMARK:
                return
            body = data[10:10 + pkg_size]
            message = json.loads(body.decode("utf-8"))
        except Exception as err:
            _LOGGER.debug("Failed to parse UDP datagram: %s", err)
            return

        msg_id = message.get("id")
        if isinstance(msg_id, int):
            fut = self._pending.get(msg_id)
            if fut is not None and not fut.done():
                fut.set_result(message)
                return

        if pkg_type in (CMD_REPORT, CMD_NOTIFY):
            for listener in tuple(self._report_listeners):
                try:
                    listener(message)
                except Exception as err:
                    _LOGGER.debug("Report listener failed: %s", err)

        for me, idx, val in _extract_state_changes(message):
            bucket = self._state_listeners.get((me, idx))
            if not bucket:
                continue
            for listener in tuple(bucket):
                try:
                    listener(val)
                except Exception as err:
                    _LOGGER.debug("State listener failed: %s", err)


def _extract_state_changes(message: Dict[str, Any]) -> list[tuple[str, str, Any]]:
    out: list[tuple[str, str, Any]] = []

    msg = message.get("msg")
    if isinstance(msg, dict):
        me = msg.get("me")
        idx = msg.get("idx")
        if isinstance(me, str) and isinstance(idx, str):
            data = msg.get("data")
            if isinstance(data, dict) and isinstance(data.get("v"), (int, float)):
                out.append((me, idx, data["v"]))
            else:
                val = msg.get("val")
                if isinstance(val, (int, float)):
                    out.append((me, idx, val))

    chg = message.get("chg")
    if isinstance(chg, list):
        for change in chg:
            if not isinstance(change, dict):
                continue
            me = change.get("me")
            if not isinstance(me, str):
                continue
            for k, v in change.items():
                if k in ("me", "agt", "agtid", "devtype", "fulltype"):
                    continue
                if isinstance(v, dict) and isinstance(v.get("v"), (int, float)):
                    out.append((me, str(k), v["v"]))

    return out


class _LifeSmartDatagramProtocol(asyncio.DatagramProtocol):
    def __init__(self, api: LifeSmartAPI) -> None:
        self._api = api

    def datagram_received(self, data: bytes, addr) -> None:
        self._api._handle_datagram(data)

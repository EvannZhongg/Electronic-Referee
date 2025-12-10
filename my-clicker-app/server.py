import asyncio
import json
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from bleak import BleakScanner, BleakClient
import pygetwindow as gw
from typing import List, Dict, Optional

# ==========================================================
# 复用原项目配置 (Config & Protocol)
# 假设这些文件在同级目录的 core/ 和 config.py 中
# 如果没有，请手动复制相关常量到这里
# ==========================================================
try:
    from config import CHARACTERISTIC_UUID, DEVICE_NAME_PREFIX
    from core.protocol import parse_notification_data
except ImportError:
    # 如果找不到文件，使用默认值作为 fallback
    CHARACTERISTIC_UUID = "025018d0-6951-4a81-de4f-453d8dae9128"
    DEVICE_NAME_PREFIX = "Counter-"
    import struct
    from dataclasses import dataclass


    @dataclass
    class ClickerEvent:
        current_total: int
        event_type: int
        total_plus: int
        total_minus: int
        timestamp_ms: int


    def parse_notification_data(data: bytes) -> ClickerEvent:
        STRUCT_FORMAT = "<ibiiI"
        if len(data) != 17: raise ValueError("Data size mismatch")
        unpacked = struct.unpack(STRUCT_FORMAT, data)
        return ClickerEvent(*unpacked)


# ==========================================================
# 1. 重写无 PyQt 依赖的核心类 (Headless Classes)
# ==========================================================

class HeadlessDeviceNode:
    def __init__(self, ble_device, on_data_callback):
        self.ble_device = ble_device
        self.client = None
        self.is_connected = False
        self.on_data_callback = on_data_callback  # 回调函数替代 Signal

    async def connect(self):
        print(f"Connecting to {self.ble_device.name}...")
        try:
            self.client = BleakClient(self.ble_device, disconnected_callback=self._on_disconnected)
            await self.client.connect()
            self.is_connected = True
            print(f"Connected: {self.ble_device.name}")
            await self.client.start_notify(CHARACTERISTIC_UUID, self._notification_handler)
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect()
        self.is_connected = False

    def _on_disconnected(self, client):
        self.is_connected = False
        print(f"Disconnected: {self.ble_device.name}")

    async def send_reset_command(self):
        if self.client and self.is_connected:
            try:
                await self.client.write_gatt_char(CHARACTERISTIC_UUID, b'\x01', response=True)
                print(f"Reset sent to {self.ble_device.name}")
            except Exception as e:
                print(f"Reset failed: {e}")

    def _notification_handler(self, sender, data):
        try:
            event = parse_notification_data(data)
            # 调用回调，将数据传给 Referee
            if self.on_data_callback:
                self.on_data_callback(
                    event.current_total, event.event_type,
                    event.total_plus, event.total_minus, event.timestamp_ms
                )
        except Exception as e:
            print(f"Parse Error: {e}")


class HeadlessReferee:
    def __init__(self, index, name, mode="SINGLE", broadcast_func=None):
        self.index = index
        self.name = name
        self.mode = mode
        self.broadcast_func = broadcast_func  # 用于向 WebSocket 广播

        self.primary_device: Optional[HeadlessDeviceNode] = None
        self.secondary_device: Optional[HeadlessDeviceNode] = None

        # 状态缓存
        self.pri_plus = 0
        self.pri_minus = 0
        self.sec_plus = 0
        self.sec_minus = 0

        self.last_total = 0
        self.last_plus = 0
        self.last_minus = 0

    def set_devices(self, primary_node, secondary_node=None):
        self.primary_device = primary_node
        if self.primary_device:
            # 绑定回调
            self.primary_device.on_data_callback = self._on_primary_data

        if self.mode == "DUAL" and secondary_node:
            self.secondary_device = secondary_node
            self.secondary_device.on_data_callback = self._on_secondary_data

    async def request_reset(self):
        tasks = []
        if self.primary_device: tasks.append(self.primary_device.send_reset_command())
        if self.secondary_device: tasks.append(self.secondary_device.send_reset_command())
        if tasks: await asyncio.gather(*tasks, return_exceptions=True)

        self.pri_plus = 0;
        self.pri_minus = 0
        self.sec_plus = 0;
        self.sec_minus = 0
        self._update_score_output()

    def _on_primary_data(self, current, evt_type, plus, minus, ts):
        self.pri_plus = plus
        self.pri_minus = minus
        self._update_score_output()

    def _on_secondary_data(self, current, evt_type, plus, minus, ts):
        self.sec_plus = plus
        self.sec_minus = minus
        self._update_score_output()

    def _update_score_output(self):
        if self.mode == "SINGLE":
            self.last_total = self.pri_plus - self.pri_minus
            self.last_plus = self.pri_plus
            self.last_minus = self.pri_minus
        else:
            # 双机模式逻辑：总分 = 主正 - 副正，重点扣分 = 主负 + 副负
            self.last_total = self.pri_plus - self.sec_plus
            self.last_plus = self.pri_plus
            self.last_minus = self.pri_minus + self.sec_minus

        # 触发广播
        if self.broadcast_func:
            data = {
                "type": "score_update",
                "payload": {
                    "index": self.index,
                    "total": self.last_total,
                    "plus": self.last_plus,
                    "minus": self.last_minus
                }
            }
            asyncio.create_task(self.broadcast_func(data))


# ==========================================================
# 2. FastAPI 服务端定义
# ==========================================================

app = FastAPI()

# 允许跨域（Electron 前端可能需要）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局状态
active_websockets: List[WebSocket] = []
referees: Dict[int, HeadlessReferee] = {}
scanned_devices_cache = []


async def broadcast_message(message: dict):
    """向所有连接的 WebSocket 客户端广播消息"""
    for connection in active_websockets:
        try:
            await connection.send_json(message)
        except WebSocketDisconnect:
            active_websockets.remove(connection)
        except Exception:
            pass


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            # 保持连接，接收心跳或其他指令
            data = await websocket.receive_text()
            # 可以在这里处理来自前端的指令，如 "reset_1"
    except WebSocketDisconnect:
        active_websockets.remove(websocket)


@app.websocket("/ws/tracking")
async def tracking_endpoint(websocket: WebSocket):
    """专门用于窗口吸附的 WebSocket"""
    await websocket.accept()
    try:
        # 1. 接收前端发来的目标窗口标题
        target_title = await websocket.receive_text()
        print(f"Start tracking window: {target_title}")

        while True:
            # 2. 在线程中执行阻塞的 pygetwindow 调用
            try:
                # 使用 to_thread 防止阻塞 asyncio 循环
                windows = await asyncio.to_thread(gw.getWindowsWithTitle, target_title)
                if windows:
                    win = windows[0]
                    # 3. 发送坐标给前端
                    await websocket.send_json({
                        "found": True,
                        "x": win.left,
                        "y": win.top,
                        "width": win.width,
                        "height": win.height,
                        "isActive": win.isActive
                    })
                else:
                    await websocket.send_json({"found": False})
            except Exception as e:
                print(f"Tracking error: {e}")

            await asyncio.sleep(0.05)  # 50ms 刷新率

    except WebSocketDisconnect:
        print("Tracking stopped")


# --- HTTP 接口 ---

@app.get("/scan")
async def scan_devices():
  """扫描蓝牙设备 (增强版：匹配名称和UUID)"""
  print("Start scanning (Enhanced Mode)...")

  # 【关键修改 1】return_adv=True 会返回广播数据，包含实时名称和 UUID
  # 返回结构: { "address": (BLEDevice, AdvertisementData) }
  devices_dict = await BleakScanner.discover(timeout=5.0, return_adv=True)

  results = []
  global scanned_devices_cache
  scanned_devices_cache = []  # 清空缓存

  print(f"Scanned {len(devices_dict)} raw devices.")

  # 目标 UUID (用于备选匹配)
  TARGET_UUID = "025018d0-6951-4a81-de4f-453d8dae9128"
  TARGET_PREFIX = "Counter-"

  for device, adv in devices_dict.values():
    # 【关键修改 2】优先获取广播包里的实时名称 (local_name)，如果没有再取缓存名称
    real_name = adv.local_name or device.name or "Unknown"

    # 调试日志：打印每一个扫到的设备，方便你看有没有信号
    print(f"  [Check] {real_name} <{device.address}>")
    print(f"       Services: {adv.service_uuids}")

    # 缓存设备对象 (连接时需要用到 device 对象，而不是 adv)
    scanned_devices_cache.append(device)

    # 【关键修改 3】双重匹配逻辑
    # 条件 A: 名称以 Counter- 开头
    match_name = real_name.startswith(TARGET_PREFIX)

    # 条件 B: 广播的服务 UUID 列表里包含我们的目标 UUID (不区分大小写)
    # 注意：有些设备广播的 UUID 是完整 128bit，有些是 16bit，这里做字符串包含检查
    match_uuid = False
    if adv.service_uuids:
      for u in adv.service_uuids:
        if str(u).lower() == TARGET_UUID.lower():
          match_uuid = True
          break

    # 只要满足任一条件，就认为是我们的设备
    if match_name or match_uuid:
      print(f"       >>> MATCHED! (Name={match_name}, UUID={match_uuid})")
      results.append({
        "name": real_name,
        "address": device.address,
        "rssi": adv.rssi
      })

  # 按信号强度排序，体验更好
  results.sort(key=lambda x: x['rssi'], reverse=True)

  return {"devices": results}


class RefereeConfig(dict):
    # 简单的字典定义，用于接收 JSON
    pass


@app.post("/setup")
async def setup_referees(config: dict):
    """
    接收前端配置，初始化裁判和连接。
    Config 示例:
    {
        "referees": [
            {"index": 1, "name": "Ref1", "mode": "SINGLE", "pri_addr": "AA:BB:...", "sec_addr": ""}
        ]
    }
    """
    global referees
    # 先清理旧连接
    for ref in referees.values():
        if ref.primary_device: await ref.primary_device.disconnect()
        if ref.secondary_device: await ref.secondary_device.disconnect()
    referees.clear()

    # 创建新裁判
    for item in config.get("referees", []):
        idx = item.get("index")
        r = HeadlessReferee(idx, item.get("name"), item.get("mode"), broadcast_message)

        # 查找设备对象
        pri_addr = item.get("pri_addr")
        sec_addr = item.get("sec_addr")

        pri_dev = next((d for d in scanned_devices_cache if d.address == pri_addr), None)
        sec_dev = next((d for d in scanned_devices_cache if d.address == sec_addr), None)

        node_pri = None
        node_sec = None

        if pri_dev:
            node_pri = HeadlessDeviceNode(pri_dev, None)  # 回调在 set_devices 里绑定
            # 异步连接
            asyncio.create_task(node_pri.connect())

        if sec_dev and item.get("mode") == "DUAL":
            node_sec = HeadlessDeviceNode(sec_dev, None)
            asyncio.create_task(node_sec.connect())

        r.set_devices(node_pri, node_sec)
        referees[idx] = r

    return {"status": "ok", "message": f"Setup {len(referees)} referees"}


@app.post("/reset")
async def reset_scores():
    """重置所有裁判分数"""
    tasks = [ref.request_reset() for ref in referees.values()]
    if tasks:
        await asyncio.gather(*tasks)
    return {"status": "reset_done"}


if __name__ == "__main__":
    # 启动服务，端口 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)

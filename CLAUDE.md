# LifeSmart Local Integration

## 規範文件
### 1. Home Assistant 2026.5.0 核心規範
詳細規範條文見 `Docs/HomeAssistant_2026.5_Rules.md`，以下為關鍵摘要：
- **全面非同步化 (Async-First):** 嚴禁使用會阻塞執行緒的函式（如 `requests`）。所有網路請求必須使用 `aiohttp`（透過 `async_get_clientsession(hass)` 取得），或使用 `hass.async_add_executor_job` 將**同步阻塞**任務交付給背景執行緒。`async_add_executor_job` 不可包裹 coroutine。
- **資料更新協調器 (DataUpdateCoordinator):** 外部 API 輪詢必須實作 `DataUpdateCoordinator`，統一管理實體 (Entities) 的資料刷新，避免重複發送請求造成效能瓶頸。
- **配置流程 (Config Flow):** 拒絕使用 `configuration.yaml` 進行設定。必須實作基於 UI 的 `ConfigFlow`，引導使用者輸入認證資訊（如 API Token、主機連線等），並確保支援認證過期後的重新設定流程 (`reauth`)。Options flow 透過 ConfigFlow class 的 `async_get_options_flow` classmethod 啟用 — **不要**在 `manifest.json` 加 `"options": true`（不是合法欄位，hassfest 會擋）。`@HANDLERS.register` 已在 HA 2026 移除。
- **型別提示 (Type Hinting):** 所有新撰寫的函式與類別方法必須包含完整的 Python 型別標註，確保能通過 `mypy` 的嚴格檢查。`Optional[callable]` 是錯誤的，應用 `Optional[Callable[[], None]]`。
- **命名規範 (Entity Naming):** 遵從 2026.5 的最新命名指引，實體名稱 (Entity Name) 內不得包含裝置名稱 (Device Name)，前端 UI 會自動完成組合。`DeviceInfo.name` 設裝置名稱；`_attr_name` 設功能描述。
- **狀態更新:** push 實體（`_attr_should_poll = False`）更新狀態時呼叫 `async_write_ha_state()`，不可呼叫 `async_update_ha_state()`（後者會觸發 poll）。
- **翻譯資料夾:** 必須用 `translations/`（複數），HA 忽略 `translation/`（單數）。
### 2. LifeSmart 規範
- LifeSmart OpenDev 1.9 → `Docs/LifeSmart OpenDEV Advanced Interface Description_1.9_20231215.md`
- Local Interfaces v1.10 → `Docs/Local Interfaces of LifeSmart Smart Station_20230926.md`
- 檢查規範相容性前必須先 `@` 重新引用 md

## 已知 firmware 行為（與規範字面不符）

- **`SL_NATURE` 內建溫度感測器：** 規範 §6.3.9 只文件化 `SL_NATURE` 的 L1/L2/L3（switch 屬性），但實際 firmware 同時提供 `T` 通道（溫度）與 `H` 通道（濕度，視型號而定）。溫度原始值為整數，需除以 10.0 還原為 °C（例如原始值 `245` → `24.5°C`）。此行為不在規範中，不得依規範字面刪除相關處理邏輯。
- **`SL_P` 窗簾狀態回報通道不明：** 規範 §6.9.1 定義 P1 為 32-bit 配置暫存器、P2/P3/P4 為控制埠、P5–P7 為 free mode 狀態感知埠，並未說明窗簾當前開閉位置用哪個通道回報。實際 firmware 可能透過 P1 的 type/val 欄位反映工作狀態，需依實機測試結果決定監聽通道。
- **未分類 `V_*` 虛擬裝置（如 `V_SI` / `me=0020`）：** 規範 §6.8/§6.9 文件化了 `V_AIR_P`（HVAC 面板）、`V_FRESH_P`（通風）、`V_DLT_645_P`（DLT 電表）、`V_IND_S`（Status Indicator）等 `V_` 前綴的虛擬裝置（hub 自建抽象）。實機觀察到還有 **`V_SI` 這類規範未文件化的 `V_*` 變體** — 推測為 hub 內部系統裝置。`me=0020` 這種低 ID 範圍（一般用戶裝置 `me` 在 `27xx`/`2dxx`）佐證了這個推測。**處理策略：保持現狀不過濾**。R8-b 的 connectivity binary_sensor 是依 `"stat" in device` 建立、不分 devtype，所以未分類的 `V_*` 裝置會跟一般裝置一樣有 connectivity entity，這是預期行為。若使用者覺得困擾、要分類處理，先在 `binary_sensor.py` / `sensor.py` 的 setup loop 加 `devtype.startswith("V_")` 條件做 INFO log dump，**從 firmware 回的 `name` / `data` / `fulltype` 欄位反推用途**，再決定是否黑名單或單獨設計處理。不要憑 devtype 字面猜測（規範也沒寫，猜了會錯）。

## Sensor 實作慣例（PROGRESS.md R7，2026-05-23）

### 電池通道對照（Local Interfaces §6.3 / §6.4）
| Devtype 前綴／代號 | 電池通道 idx | 來源章節 |
|---|---|---|
| `SL_SW_ND*`（Stellar/Starry/Polar Switch，含 `_V*`） | `V` | §6.3.2 |
| `SL_MC_ND*`（Multi-control Accessory，含 `_V*`） | `V` | §6.3.5 |
| `SL_SC_BB` / `SL_SC_BB_V2`（CUBE Clicker） | `V` | §6.3.6 / §6.3.7（**尚未支援**） |
| `SL_P`（MINS 窗簾） | `P8` | §6.4.3 |
| 其他 switch 系列（`SL_SW_NS*`、`SL_SW_BS*`、`SL_SW_MJ*`、`SL_SW_IF*`、`SL_SW_RC*`、`SL_SW_CP*`、`SL_NATURE` …） | **無電池通道** | §6.3.1 / §6.3.3 / §6.3.4 / §6.3.8 / §6.3.9 |

建立電池 sensor 前必須 `"V" in device["data"]`（或對應 idx）守門 — 規範說有的型號不代表所有 firmware 都會送，沒送就不建。

### HA 2026.5 命名規範實作模板（所有 sensor 子類別共用）
- `DeviceInfo.name = device.get('name', '...')` — 設裝置名稱（基底類 `LifeSmartBaseSensor.__init__` 已處理）
- `_attr_name = "<功能單字>"` — 例如 `"Battery"`、`"Temperature"`；**不可** 含 `device['name']` 或裝置名稱
- HA 前端會自動組合 `"<裝置名稱> <功能>"`，視覺與舊版相同但符合規範
- 補完：`_attr_device_class` + `_attr_state_class`（電池 → `BATTERY` + `MEASUREMENT`；溫度 → `TEMPERATURE` + `MEASUREMENT`）— 影響圖示、低電量警告、統計圖

### `LifeSmartBatterySensor` 通用化（避免再寫死 idx）
- `__init__` 用 `device.get("data", {}).get(idx, {}).get("v")` 取初值，**禁止寫死** `data["P8"]` / `data["V"]`
- 同一個類別同時服務 MINS Curtain (P8) 與 ND-series Switch (V)，由 `async_setup_entry` 決定傳哪個 idx

### `LifeSmartSignalSensor` 設計（device-level 屬性的範例）
- `lDbm` 不在 `data[idx]` 內、是 device 頂層屬性 → 建構時傳 `idx=None` 給 base，**不註冊 state listener**
- entity_id 用虛擬 idx `"signal"` 走 `generate_entity_id()` 產生 → `sensor.<devtype>_<agt>_<me>_signal`
- unique_id 用 `signal_<me>`（pattern 與 `temp_<me>`、`battery_<me>` 一致）
- 純輪詢更新：`_async_update` 走 `ep` GET 取 `response["msg"]["lDbm"]`
- 屬性：`SIGNAL_STRENGTH` device_class + `MEASUREMENT` state_class + `SIGNAL_STRENGTH_DECIBELS_MILLIWATT` 單位 + `EntityCategory.DIAGNOSTIC`（避免污染主畫面）
- **未來新增 device-level 屬性的 sensor（如 `epver`、`valts`）建議依此 pattern**：idx=None + 虛擬 idx 字串給 entity_id + 自帶輪詢

### `LifeSmartCoordinator` 用法（D15 起，2026-05-24）
> 新增「會定期讀資料」的 entity **必走** [coordinator.py](custom_components/lifesmart/coordinator.py)，不要再用 `async_track_time_interval`。對 N 個 entity 的 hub，輪詢請求量從 N 降為 1。

- coordinator 由 [__init__.py `async_setup_entry`](custom_components/lifesmart/__init__.py) 建立並存進 `entry_data["coordinator"]`；種子資料來自 discovery 結果（無需第一次輪詢延遲）
- 平台檔（如 sensor.py）setup 時 `coordinator = entry_data.get("coordinator")`，傳給每個 entity 的 `__init__`
- entity 構造時呼叫 `super().__init__(api, device, idx, coordinator=coordinator)` — base class 的 `async_added_to_hass` 會自動 `coordinator.async_add_listener(self._handle_coordinator_update)`
- 子類別 override `_handle_coordinator_update`：
  ```python
  def _handle_coordinator_update(self) -> None:
      device = self._device_from_coordinator()  # base helper, 回傳 coordinator.data[me]
      if device is None:
          return
      raw = device.get("data", {}).get(self._idx, {}).get("v")  # 或頂層屬性如 lDbm
      if isinstance(raw, (int, float)):
          self._attr_native_value = int(raw)  # 或對應轉換
          if self.hass:
              self.hass.async_create_task(self._async_write_state())
  ```
- 範本：sensor.py 的 [LifeSmartTemperatureSensor](custom_components/lifesmart/sensor.py) / [LifeSmartBatterySensor](custom_components/lifesmart/sensor.py) / [LifeSmartSignalSensor](custom_components/lifesmart/sensor.py)
- **Push 路徑 (state_listener) 與 coordinator 並行不衝突** — push 提供即時更新、coordinator 提供 15min 後備
- **尚未搬到 coordinator 的舊代碼**：`binary_sensor.py` connectivity sensor、`cover.py` — 留作 R13 follow-up，遵循上述 pattern 即可

### `LifeSmartConnectivitySensor` 設計（device-level 屬性 + push 派發的範例）
- 規範裡 `stat` 是 scalar（不是 `{v: ...}` 結構），原本 `api._extract_state_changes` 只處理 dict-with-v 的 channel value，會把 stat 跳過
- 解法：`api.py` 在 `chg` 解析迴圈中對 `k == "stat" and isinstance(v, (int, float))` 額外 emit `(me, "stat", v)` — `"stat"` 是**虛擬 idx**，讓既有 `register_state_listener(me, idx, cb)` 機制能直接派發 device-level scalar 屬性
- `LifeSmartConnectivitySensor` 同時走 push（`register_state_listener(me, "stat", cb)`）與 15 min 後備輪詢（`ep` GET 取 `msg.stat`），push 漏失也不會卡在錯誤狀態
- entity_id 用虛擬 idx `"connectivity"`；unique_id `connectivity_<me>`
- 屬性：`BinarySensorDeviceClass.CONNECTIVITY` + `EntityCategory.DIAGNOSTIC`
- **未來如要 push 更新其他 device-level scalar 屬性**（例如 `epver` 變動）：先擴充 `api._extract_state_changes` 加入相應的 scalar 分支，再用虛擬 idx 模式註冊 listener — 不要另寫獨立的 listener 機制

## Hub 層級功能（PROGRESS.md R8 / R9，2026-05-23 — Phase 1 + Phase 2 起始項已完成）

> Phase 1 hub 自身的版本／重啟／場景已完成（R9）。子裝置層面的訊號（R8-a `lDbm`）與連線（R8-b `stat`）也已完成。剩下的是 Phase 2 中後段與 Phase 3。

### 已實作的 hub 命令
- `cfg:notify`（LI §3.3.10）— [api.py `configure_event_service`](custom_components/lifesmart/api.py)；啟動時呼叫，**`__init__.py` 已每 90s 重打**（規範要求 300s 內重新訂閱）
- `cfg:getver`（LI §3.3.10）— [api.py `get_hub_version`](custom_components/lifesmart/api.py)；R9 setup 時打一次存進 `entry_data["hub_info"]`，餵給 3 個 `LifeSmartHubInfoSensor`。R12/D17 失敗時自動 `ir.async_create_issue("hub_version_unknown")`
- `cfg:reboot`（LI §3.3.10）— [api.py `reboot_hub`](custom_components/lifesmart/api.py)；R9 `LifeSmartHubRebootButton` 觸發
- `scene` GET（LI §3.3.5）— [api.py `get_scene_list`](custom_components/lifesmart/api.py)；R9 `scene.py` setup 時跑一次拉清單
- `doscene` SET（LI §3.3.6）— [api.py `trigger_scene`](custom_components/lifesmart/api.py)；R9 HA Scene `async_activate` 觸發
- `eps`（LI §3.3.2）— `discover_devices()` 取子裝置清單（**含 `lDbm` 公共屬性**）。R12/D15 起也由 [LifeSmartCoordinator](custom_components/lifesmart/coordinator.py) 週期性呼叫（15 min）餵給 sensor 平台 — 控制 hub 請求量
- `ep` GET / SET（LI §3.3.1 / §3.3.3）— switch 控制與一次性 init 讀；舊式 sensor 也透過 `ep` GET 做一次性 init（之後改吃 coordinator 更新）
- `rssi`（LI §3.3.9）— 帶 `me` 取子裝置訊號（hub 自身用法未驗證）
- `spotremote`（IR remote）— get list / get keys / send key

### 子裝置公共屬性（LI §6.1）— signal / connectivity sensor 的依據
每個 sub-device 在 `eps` / `ep` 回應頂層除 `devtype`/`me`/`name`/`agt`/`data` 外還含：
- **`stat`**：1=online、0=offline（R8-b 已實作為 CONNECTIVITY binary_sensor，push + 15min 後備輪詢）
- **`lDbm`**：dBm 整數，device→hub 訊號強度（R8-a 已實作為 diagnostic sensor）
- `epver`：sub-device 韌體版本（已用作 `DeviceInfo.sw_version`）
- `valts`：最後屬性變動時戳 (ms)（尚未使用）

### 已知缺漏 / 計畫實作（依 R8 phase 排序）
| Phase | 命令／事件 | 規範 | 對應 HA 實體 | 狀態 |
|---|---|---|---|---|
| 1 | `cfg:getver` | LI §3.3.10 | 3× diagnostic sensor（韌體版本／系統版本／hub 型號）| **✅ R9** |
| 1 | `cfg:reboot` | LI §3.3.10 | `button`（`device_class=RESTART`）| **✅ R9** |
| 1 | scene list / trigger | LI §5 | HA `scene` 平台（先支援 `cls=scene` / `groupirc`）| **✅ R9** |
| 1+ | **`lDbm` (LI §6.1) per-device** | LI §6.1 | per-device `SIGNAL_STRENGTH` diagnostic sensor | **✅ R8-a** |
| 2 | **NOTIFY `chg.stat`** | LI §4 / §6.1 | per-device `binary_sensor`（CONNECTIVITY）| **✅ R8-b** |
| 2 | hub `rssi`（不帶 `me`）| LI §3.3.9 | 3× diagnostic sensor **[未驗證]** | ❌ |
| 2 | `cfg:timezone` | LI §3.3.10 | sensor + service | ❌ |
| 3 | `cfg:reset` / `cfg:upgrade` / `cfg:devname` | LI §3.3.10 | service（confirmation 必須）| ❌ |
| 3 | `cfg:net getifn` | OD §2.3.4 | diagnostic sensor（DEFED 機型限定）| ❌ |

### Hub 型號對照（`cfg:getver` 回傳的 `mgatype`，LI §3.3.10 L1561-1576）
- `LSJZX1K` → Smart Station / Smart Station Pro
- `LSSSMINIV1` → Smart Station Mini
- `LSNAMIV1` → NatureMini
- `LSNAMIV3` → NatureMini Pro
- `LSNAMIV4` → NatureMini L
- `LSMGANAV1` → NatureMini S / Nature 7
- `LSHI3518` → Old version of Smart Station

### 實作注意事項
- **`cfg:notify` 每 300s 失效**（LI §4 L1603）— [__init__.py:86](custom_components/lifesmart/__init__.py:86) 已每 90s 跑一次 `_refresh_notify`，不需要再加任何重訂閱邏輯。（先前 R8 規劃時誤標為「潛在 bug」，2026-05-23 重讀代碼確認已處理。）
- **`cfg:reboot` / `cfg:reset` 收到立刻執行** — 沒有規範層級的 confirmation。`cfg:reboot` 已用 `ButtonDeviceClass.RESTART`（HA UI 自帶確認 prompt）；未來做 `cfg:reset` 必須走 service + `services.yaml` `confirmation: true`。
- **`rssi` 不帶 `me` 取 hub 自身訊號是語意推論**（規範原文有 typo「If there is no is in me」），實作前要實機驗證。
- **scene `id` 是 `AI...` 字串**，不是數字（LI §5.1 L1719）。
- **`cfg:net` (OD §2.3.4) 僅 DEFED 機型支援** — 實作前用 `cfg:getver` 判斷 `mgatype` 才建立。

### Hub-level entity 組織慣例（為 Phase 1 預先確立，未來實作必須遵循）

> 目前所有 entity 都掛在 sub-device 的 `DeviceInfo`（識別 = `(DOMAIN, device['me'])`）。Phase 1 hub 自身的 entity（韌體版本 sensor / reboot button / scenes）沒有 `me`，需要一個獨立的 "hub" device 把它們群組在一起，否則 HA UI 會散亂成一堆無主 entity。

**Hub DeviceInfo 模板：**
```python
hub_identifier = f"hub_{config_entry.data[CONF_HOST]}"  # 短期：用 host IP
# 未來改進：從 §2 discovery 抓 SN 存進 config_entry.data，再改用 SN
self._attr_device_info = DeviceInfo(
    identifiers={(DOMAIN, hub_identifier)},
    name=config_entry.title or "LifeSmart Hub",
    manufacturer=MANUFACTURER,
    model=mgatype,         # 來自 cfg:getver，例如 "LSJZX1K"
    sw_version=ver,        # 來自 cfg:getver
    # 不要設 via_device — hub 是頂層裝置
)
```
- **不要**用 `config_entry.entry_id` 作 identifier — 它會在使用者移除／重加整合時換掉，把 device registry 弄孤
- **要**用 stable 屬性（host IP，或更好的 SN）。HA device registry 會跨重啟保留。
- 子裝置的 `DeviceInfo` 加 `via_device=(DOMAIN, hub_identifier)` 就能讓 UI 顯示「hub → sub-devices」的階層

**entity_id / unique_id 模板（hub-level）：**
- unique_id：`hub_<功能>_<host>`，例如 `hub_firmware_192_168_1_50`、`hub_reboot_192_168_1_50`
- entity_id：`<platform>.lifesmart_hub_<功能>`（**手動寫**，不走 `generate_entity_id`，因為沒有 devtype/me）
- 範例：`sensor.lifesmart_hub_firmware_version`、`button.lifesmart_hub_reboot`、`sensor.lifesmart_hub_mgatype`

**Scene 平台特例（LI §5）：**
- Scene id 是 `AI...` 字串、不是 `me` → unique_id 用 `scene_<AI_id>`、entity_id `scene.lifesmart_<slugified_name>_<AI_id_tail>`
- 每個 scene 是獨立 HA `scene` 實體，**不掛**在 hub device 下（HA scene 平台慣例不掛 device）
- `cls in ("scene", "groupirc")` 是純觸發（無參數），最簡單；`cls in ("groupsw", "grouphw", "grouprgbw")` 帶 on/off + 顏色參數，先不做（或做成 `light`/`switch` 而非 `scene`）

**初次 setup 取得 hub 資料的順序：**
1. config_flow 完成 → `async_setup_entry` 啟動 api
2. 在 setup 早期呼叫一次 `cfg:getver` 把 `ver` / `osver` / `mgatype` 存進 `entry_data["hub_info"]`
3. 所有 hub-level entity 都從 `entry_data["hub_info"]` 拿資料，不要每個 entity 各自再打一次 `cfg:getver`
4. 後續更新 `cfg:getver` 只跑慢輪詢（24h 即可，韌體版本不會頻繁變）

**R9 已實作部分（2026-05-23）：**
- `entry_data["hub_info"]` cache 已在 [__init__.py](custom_components/lifesmart/__init__.py) `async_setup_entry` 建立（single-shot；尚無 24h 輪詢，韌體變動需 reload 才會反映）
- `entry_data["host"]` 也存進 entry_data，給 hub-level entity 拼 `hub_identifier` 與 `host_slug` 用
- `LifeSmartHubInfoSensor`（sensor.py 末）/ `LifeSmartHubRebootButton`（button.py）共用 `f"hub_{host}"` 作為 DeviceInfo identifier
- `LifeSmartScene`（scene.py）**不掛**在 hub DeviceInfo 下（HA scene 慣例）— unique_id `scene_<AI_id>`，entity_id `scene.lifesmart_<name_slug>_<id_tail>`
- 子裝置目前**還沒**加 `via_device=(DOMAIN, hub_identifier)` — 未來想做 hub→sub-device 階層展示時要在 sensor/switch/cover/binary_sensor/remote 五個平台檔的 DeviceInfo 一次性加上

## 技術債清單（PROGRESS.md R11，2026-05-24 盤點 / R12 已修 P3 全部）

> 完整 22 項在 PROGRESS.md R11，依「確定性 × 嚴重性」分 5 級。R12（PROGRESS）已修 P3 全部 7 項（D11-D17）；剩下 P0 (D1-D3) + P1 (D4-D7) + P2 (D8-D10) + P4 (D18-D22)。下面只列 **🔴 P0** 與動工前必看的 P1 注意事項。

### 🔴 P0 動工前必驗證
- **D1 `cover.py` PORT_STATE = "P1"** — [cover.py:17](custom_components/lifesmart/cover.py:17)：規範 §6.9.1 P1 為配置暫存器，實際狀態通道不明；動 cover 邏輯前先看 NOTIFY 載荷確認哪個通道真正反映行程狀態
- **D2 Scene `args.args.type=128`** — [api.py:186-196](custom_components/lifesmart/api.py:186)：硬抄規範範例 L1077；對 `cls=scene` / `groupirc` 是否真有效未驗證，hub 可能回 code=0 但不執行；動 scene.py 前先實機確認
- **D3 `rssi` 不帶 `me` 取 hub 訊號** — 規範原文 typo「If there is no is in me」；尚未實作（R8 Phase 2），實作前必須先實機驗證才能上 code

### 🟠 P1 動到相關區域時要記得
- **D4** `hub_info` 是 setup-time single-shot；改 hub-level entity 時記得韌體升級不會反映
- **D5** Reboot button 按完不會 re-discover；動 button.py 時順手加排程 reload
- **D6** NOTIFY `add` / `del` 事件未處理，新配對裝置不會自動出現；動 api.py `_extract_state_changes` 時可順手加 listener 觸發 `async_reload`
- **D7** 首次 setup 看到離線裝置會直接建 `is_on=False`；改 binary_sensor.py 時記得改成初值 `unknown`

### 「投資報酬最高的小改」（隨時可動）
- **D22 sub-device DeviceInfo 加 `via_device=(DOMAIN, hub_identifier)`** — 5 個平台檔（sensor/switch/cover/binary_sensor/remote）；UI 直接出現 hub→sub-device 階層；單次改完不會回頭

### P3 已全修（R12，2026-05-24）— 寫新代碼時的慣例
- **D11**：除非是 callback dispatcher（已有 `# noqa: BLE001` 註解），**不要**寫 `except Exception`。用具體型別 `(asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError)` 或對應的 stdlib 例外。
- **D12**：純函式優先寫 test 進 `tests/`。conftest 有 HA stubs，跑 `/tmp/lifesmart_pytest_venv/bin/python -m pytest tests/` 即可。新功能附測試。
- **D13**：config_flow 加新欄位、`ir.async_create_issue` 加新 issue → 三份 translations（en.json / zh-Hant.json / zh-Hans.json）一起改。
- **D14**：改 `entry.data` 結構必須 bump `ConfigFlow.VERSION` 並在 `async_migrate_entry` 加對應分支。
- **D15**：新 polling sensor／binary_sensor／cover 一律走 `LifeSmartCoordinator`（[coordinator.py](custom_components/lifesmart/coordinator.py)）：constructor 接 `coordinator` 參數、override `_handle_coordinator_update` 從 `coordinator.data[me]` 取值。**不要**再用 `async_track_time_interval`。
- **D16**：debug device payload → 看 HA UI「下載診斷」，不要再加臨時 log。`diagnostics.py` 已含敏感欄位 redact。
- **D17**：使用者可採取動作的失敗（hub unreachable、`cfg:getver` 不認）→ 用 `ir.async_create_issue` 而非單純 log；成功時 `ir.async_delete_issue` 清除。

### 仍待處理（按 R11 ROI 排序）
1. D2 Scene `type=128` 實測（Phase 1 部署順手）
2. D1 cover P1 通道實測
3. D22 sub-device DeviceInfo 加 `via_device`（最高 ROI 小改）
4. D6 NOTIFY add/del 處理（自動感知新裝置）
5. D15 follow-up：binary_sensor + cover 也搬到 coordinator

完整單與分項詳細：[PROGRESS.md「技術債盤點（R11）」段](PROGRESS.md) 與 R12 進度

---

## 命名規則（PROGRESS.md R6，2026-05-18 確立）

> 歷史：R5 曾為了與舊整合並存而在 entity_id/unique_id 加 `lls_` 前綴並把 domain 改為 `lls`。R6 全面 revert — 改為直接取代舊整合，**不再使用任何 `lls` 字樣**。

- **資料夾：** `custom_components/lifesmart/`（不是 `lls/`）
- **Domain：** `lifesmart`（`manifest.json` 與 `const.py` 的 `DOMAIN`）
- **整合顯示名稱：** `Local LifeSmart`（不帶 `(LLS)` 後綴）— `manifest.json`、`hacs.json` 一致
- **`generate_entity_id()`（`__init__.py`）：** 回傳 `re.sub(r"_+", "_", f"{devtype}_{agt}_{me}_{idx}".lower()).strip("_")`，**不加任何前綴**
- **unique_id 模板（R10 起，2026-05-24）：**
  - `switch`：`switch_<agt>_<me>_<idx>`
  - `sensor`：`temp_<agt>_<me>` / `battery_<agt>_<me>` / `signal_<agt>_<me>`
  - `binary_sensor`：`connectivity_<agt>_<me>`
  - `cover`：`cover_<agt>_<me>`
  - `remote`：`remote_<agt>_<me>`
  - hub-level（不跟 sub-device）：`hub_<feature>_<host_slug>`、scene `scene_<AI_id>`
  - **重點：必須包含 `agt`（hub ID）** — `me` 只在單 hub 內唯一；hub 自建的系統裝置（如 `V_SI / me=0020`）會在每個 hub 重複出現，沒加 agt 會跨 hub 撞號（[__init__.py `_migrate_unique_ids`](custom_components/lifesmart/__init__.py) 會自動把舊格式 in-place 改寫成新格式，使用者不會丟自動化）
- **entity_id 模板：**
  - `switch/sensor/cover/binary_sensor`：透過 `generate_entity_id`，格式為 `<platform>.<devtype>_<agt>_<me>_<idx>`（全 lower-case）
  - `remote`（R10-b 起，2026-05-24）：`remote.<slugify(device.name)>_<agt>_<me>`（不走 `generate_entity_id`，但同樣含 agt 避免跨 hub 撞號）；[remote.py:80-87](custom_components/lifesmart/remote.py:80) 有 in-place rename 機制把舊格式 `remote.<name>_<me>` 自動改名到新格式
  - hub-level（手寫）：`<platform>.lifesmart_hub_<功能>`、scene `scene.lifesmart_<name_slug>_<id_tail>`
- 修改命名規則前必讀 PROGRESS.md R5/R6，不要在沒有明確指示下重新引入 `lls_` 前綴或改回並存策略。

## 工作習慣
- 規範比對前先讀 `Docs/`，不可依賴記憶或推測
- 結論必須標註來源章節
- 不確定時明說「未驗證」，不要猜
- 程式碼修改前先確認 HA 2026.5 規範

## 目標環境
- HA 2026.5+（不需向下相容）
- **本整合為純 backend Python**（無 `frontend/` / `panel*.js` / Lovelace card 資源）— 因此 HA 前端規範變動（例如 2026-03 的 [Frontend Lazy Context](https://developers.home-assistant.io/blog/2026/03/25/frontend-lazy-context/) 取代 `SubscribeMixin`）**對本專案不適用**；前端與我們的互動完全透過標準 entity platform API。下次被問到類似的前端公告時，直接套這個結論、不必再讀文章。
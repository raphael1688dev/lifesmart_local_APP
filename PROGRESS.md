# Code Review Progress

## 代碼語法與語意全檢 — 2026-05-16（第二次，含規範比對）

來源縮寫：
- **[HA]** = HA 2026.5 規範（`Docs/HomeAssistant_2026.5_Rules.md`）
- **[LI §X]** = Local Interfaces v1.10（`Docs/Local Interfaces of LifeSmart Smart Station_20230926.md`）
- **[OD §X]** = OpenDev 1.9（`Docs/LifeSmart OpenDEV Advanced Interface Description_1.9_20231215.md`）
- **[未驗證]** = 邏輯推斷，未找到規範明確條文

---

### 嚴重 Bug（C — Critical）

- [x] **C1 Domain 名稱不一致**
  - 資料夾改名 `local_lifesmart` → `LocalLifeSmart`
  - `manifest.json` `"domain"` 改為 `"local_lifesmart"`
  - `const.py` `DOMAIN` 改為 `"local_lifesmart"`
  - 注意：macOS 檔案系統不區分大小寫，`LocalLifeSmart` 可對應 `local_lifesmart`；Linux 伺服器若需嚴格一致，資料夾須改回 `local_lifesmart`
  - 來源：**[HA]** manifest domain == folder rule

- [x] **C2 `_async_update_data` 定義兩次且呼叫不存在的方法**
  - 修復：刪除整個 `coordinator.py`（死程式碼）

- [x] **C3 Coordinator 呼叫四個不存在的 API 方法**
  - 修復：刪除整個 `coordinator.py`（死程式碼）

- [x] **C4 初始化屬性放錯位置**
  - 修復：刪除整個 `coordinator.py`（死程式碼）

- [x] **C5 `async_add_executor_job` 包裹 coroutine**
  - 修復：刪除整個 `coordinator.py`（死程式碼）

- [x] **C6 `_async_refresh_data` 靜默跳過所有遙控器**
  - `remote.py`：`isinstance(keys, list)` → `isinstance(keys, dict)`；區域變數 `remote` 改名為 `remote_info`
  - 來源：**[OD §2.2.2]** getkeys 回傳 dict

---

### 邏輯 Bug（L — Logic）

- [x] **L1 溫度推播值未除以 10**
  - `sensor.py`：`LifeSmartTemperatureSensor` 新增 `_handle_state_value` override，推播值 `÷ 10.0`

- [x] **L2 `cover.py` 觸發不必要的 poll**
  - `cover.py:126`：`async_update_ha_state()` → `async_write_ha_state()`
  - 來源：**[HA]** `async_write_ha_state` for push entities

- [ ] **L3 `cover.py` 監聽錯誤埠位 P1** 【未驗證，保留待實機測試】
  - `cover.py:67-68`：`PORT_STATE = "P1"` — 規範 P1 為配置暫存器，真實狀態通道不明
  - 來源：**[LI §6.9.1]**（未驗證）

- [x] **L4 `remote.py` `split("::")` 缺少 maxsplit**
  - `remote.py:222`：`cmd.split("::")` → `cmd.split("::", 1)`

- [x] **L5 `switch.py` DeviceInfo 命名違反 HA 2026.5**
  - `switch.py`：`async_setup_entry` 傳入 `channel_name` 取代 `"{device_name} {channel_name}"`；`DeviceInfo.name` 改用 `device.get('name')`
  - 來源：**[HA]** Entity Naming rule

- [x] **L6 `remote.py` 區域變數遮蔽模組**
  - `remote.py:152`：`remote = ...` 改名為 `remote_info = ...`（隨 C6 一併修復）

- [x] **L7 code 101 重試無實際效果** 【未驗證】
  - `__init__.py`：移除無效的 `asyncio.sleep(1)`；改為 `_LOGGER.warning` 提示操作者確認主機時鐘同步

- [x] **L8 `sensor.py` 硬編碼索引鍵**
  - `sensor.py:202`：`response["msg"]["data"]["T"]["v"]` → `response["msg"]["data"][self._idx]["v"]`

---

### 警告（W — Warning）

- [x] **W1 `manifest.json` `options:true` 但無對應 flow**
  - `config_flow.py`：新增 `LifeSmartOptionsFlowHandler` 及 `async_get_options_flow`
  - 來源：**[HA]** Config Flow rule

- [x] **W2 翻譯資料夾重複且舊資料夾無效**
  - 刪除 `translation/`（舊，HA 忽略）；`translations/en.json` 補充 `reconfigure` 與 `options.step.init` 翻譯
  - 來源：**[HA]** translations folder (plural)

- [x] **W3 `config_flow.py` 使用已移除/棄用的 API**
  - `config_flow.py`：移除 `@config_entries.HANDLERS.register(DOMAIN)` 與 `CONNECTION_CLASS`
  - 來源：**[HA]** Config Flow rule

- [x] **W4 硬編碼真實 token 作為預設值**
  - `config_flow.py`：移除 `CONF_TOKEN` 的 `default="8SptZ2l2xnQlb8bSdT8mwA"`

- [x] **W5 `sensor.py` 型別標註錯誤**
  - `sensor.py`：`Optional[callable]` → `Optional[Callable[[], None]]`，`Callable` 加入 typing 匯入
  - 來源：**[HA]** Type Hinting rule

- [x] **W6 `api.py` 未使用的 import**
  - `api.py:3`：移除 `import socket`

- [x] **W7 `coordinator.py` 整體從未被使用**
  - 修復：刪除整個 `coordinator.py`

- [x] **W8 `get_remote_list` 回傳型別標註錯誤**
  - `api.py`：`Dict[str, Any]` → `list`

- [x] **W9 logging 使用 f-string（多處）**
  - `sensor.py`、`__init__.py`：所有 `_LOGGER.xxx(f"...")` 改為 `_LOGGER.xxx("...", var)` 格式

- [x] **W10 `generate_entity_id` 條件判斷錯誤**
  - `__init__.py`：`if idx:` → `if idx is not None:`

- [x] **W11 `services.yaml` 缺少 selector 定義**
  - `services.yaml`：`remote_id` 和 `keys` 欄位各補充 `selector: text:`
  - 來源：**[HA]** services.yaml selector format

---

---

## 第三輪檢查新發現（2026-05-16）

### 邏輯 Bug

- [x] **N-L1 `api.py` `get_remote_list` 失敗分支回傳 dict 而非 list**
  - 失敗時 `return response`（dict）→ 改為 `return []`
  - 影響檔案：`api.py`

- [x] **N-L2 `config_flow.py` `if devices:` 永遠通過**
  - `discover_devices()` 回傳任何 dict 皆為 truthy，即使連線失敗也建立 entry
  - 改為明確驗證 `code == 0` 且 `msg` 為非空 list
  - 影響檔案：`config_flow.py`（`async_step_user` 與 `async_step_reconfigure` 皆修復）

- [x] **N-L3 `remote.py` `_attr_name` 含裝置識別碼**
  - `f"{name}_{device['me']}"` → `name`
  - 影響檔案：`remote.py`

### 警告

- [x] **N-W1 `cover.py` 硬編碼 `"LifeSmart"` 未使用常數**
  - 補充 `MANUFACTURER` 匯入，`manufacturer="LifeSmart"` → `manufacturer=MANUFACTURER`
  - 影響檔案：`cover.py`

- [x] **N-W2 `switch.py` `VAL_TYPE_ONOFF` 匯入但未使用**
  - 從 import 移除 `VAL_TYPE_ONOFF`
  - 影響檔案：`switch.py`

- [x] **N-W3 `switch.py` 大段註解舊代碼未清除**
  - 移除 `_async_update_state` 內 7 行被註解的舊 args/response 模式
  - 影響檔案：`switch.py`

- [x] **N-W4 `sensor.py` 冗餘 f-string**
  - `f"{device.get('name', 'Temperature Sensor')}"` → `device.get('name', 'Temperature Sensor')`
  - 影響檔案：`sensor.py`

- [x] **N-W5 `sensor.py` 模組匯入置於 `__init__` 內部**
  - `from . import generate_entity_id` 移至模組頂層
  - 影響檔案：`sensor.py`

- [x] **N-W6 `__init__.py` 型別標註不含 `None`**
  - `api: LifeSmartAPI` → `api: Optional[LifeSmartAPI]`，補充 `from typing import Optional`
  - 影響檔案：`__init__.py`

---

### 累計統計

| 嚴重程度 | 數量 | 已修復 |
|---------|------|--------|
| 嚴重 Bug（C） | 6 | 6 |
| 邏輯 Bug（L） | 11 | 10 |
| 警告（W） | 17 | 17 |
| **合計** | **34** | **33** |

**剩餘 1 項：**
- L3：P1 狀態通道未驗證（需實機測試）

---

## 第四輪修復（2026-05-16，實機測試後）

### 嚴重 Bug

- [x] **R1 簽名雙逗號導致 hub 一律回傳 code 101**
  - `api.py`：`_create_signature` 使用 f-string 拼接，`args` 為空時產生 `"obj:eps,,ts:..."` 雙逗號，簽名永遠錯誤
  - 改為逐欄位 `parts.append()`，空 args 時直接接 `ts`，不產生多餘逗號
  - 影響：`discover_devices()` 從未能正常驗簽；`config_flow` 一律顯示「找不到設備」
  - 來源：**[LI §3.2.1]** 簽名格式規範

### 邏輯 Bug

- [x] **R2 `config_flow` 不接受 `msg` 為 dict 格式**
  - 驗證條件 `isinstance(msg, list)` 無法處理 hub 回傳 dict（以設備 ID 為鍵）的情況
  - 新增 `_has_devices(msg)` helper，同時接受 list 與 dict

- [x] **R3 code 101 重試未校正時間戳記**
  - `api.py`：新增 `ts_offset: int = 0` 與 `apply_ts_from_response()`
  - `config_flow.py` + `__init__.py`：偵測 code 101 → `apply_ts_from_response()` → 重試
  - 注意：R1 修復後 101 幾乎不再出現；此機制作為時鐘真正偏移時的安全網

### 命名與版本

- [x] **R4 整合名稱與版本更新**
  - `manifest.json`：`name` → `"Local LifeSmart (LLS)"`，`version` → `"20260516r4"`
  - `hacs.json`：`name` → `"Local LifeSmart (LLS)"`

### 並存支援

- [x] **R5 entity_id 與 unique_id 全面加 `lls_` 前綴**
  - `__init__.py`：`generate_entity_id()` 回傳 `"lls_" + slug`
  - `switch.py`：unique_id `lls_switch_<dev>_<idx>`
  - `sensor.py`：unique_id `lls_temp_<dev>`、`lls_battery_<dev>`
  - `cover.py`：unique_id `lls_cover_<dev>`
  - `remote.py`：unique_id `lls_remote_<dev>`；entity_id `remote.lls_<name>_<dev>`

- [x] **R6 ~~R5~~ 全面 revert：放棄並存策略，改為取代舊整合** — 2026-05-18
  - 動機：並存方案 (R4/R5) 在實機驗證上沒有實益，決定直接覆寫舊版的 entity registry
  - 資料夾：`custom_components/lls/` → `custom_components/lifesmart/`
  - `manifest.json`：`domain` `"lls"` → `"lifesmart"`；`name` `"Local LifeSmart (LLS)"` → `"Local LifeSmart"`
  - `hacs.json`：`name` `"Local LifeSmart (LLS)"` → `"Local LifeSmart"`
  - `const.py`：`DOMAIN = "lifesmart"`
  - `__init__.py`：`generate_entity_id()` 不再加任何前綴，回傳 `re.sub(r"_+", "_", raw).strip("_")`
  - `switch.py`：unique_id `switch_<dev>_<idx>`
  - `sensor.py`：unique_id `temp_<dev>`、`battery_<dev>`
  - `cover.py`：unique_id `cover_<dev>`
  - `remote.py`：unique_id `remote_<dev>`；entity_id `remote.<name>_<dev>`
  - 結果：給定相同 `devtype/agt/me/idx`，entity_id 字面與舊代碼一致；unique_id 撞號 → 部署時須先移除舊整合再重新加入

### Sensor 擴充與規範對齊

- [x] **R7 Switch 電池 sensor 支援 + HA 2026.5 命名規範對齊** — 2026-05-23 — `manifest.json` version `20260523r0`
  - 動機：Local Interfaces §6.3.2 / §6.3.5 明文 `SL_SW_ND*` / `SL_MC_ND*` 有 `V` 通道回報電量，但 `sensor.py` 只有 `SL_P` + `P8` 的分支。
  - `sensor.py` — `async_setup_entry` 新增分支：當 `devtype.startswith(("SL_SW_ND", "SL_MC_ND"))` 且 `data` 含 `V` 時建立 `LifeSmartBatterySensor(idx="V")`。
  - `sensor.py` — `LifeSmartBatterySensor.__init__` 修正 bug：原本寫死 `device["data"]["P8"]["v"]`，改為 `device["data"][idx]["v"]`。
  - `sensor.py` — `LifeSmartBatterySensor._attr_name` `"{device name} Battery"` → `"Battery"`；補 `SensorDeviceClass.BATTERY` + `SensorStateClass.MEASUREMENT`。
  - `sensor.py` — `LifeSmartTemperatureSensor._attr_name` `device.get('name', ...)` → `"Temperature"`；補 `SensorDeviceClass.TEMPERATURE` + `SensorStateClass.MEASUREMENT`。
  - HA 2026.5 命名規範：`_attr_name` 只設功能；裝置名稱由 `DeviceInfo.name` 提供，HA 前端自動組合 → 視覺結果與舊版相同。
  - 已知未涵蓋：CUBE Clicker (`SL_SC_BB` / `SL_SC_BB_V2`) 的 V 通道；`SL_MC_ND*` 的 L1/L2/L3 switch 與 B1/B2/B3 button 通道。

### Hub 層級功能研究（規劃，尚未實作）

- [x] **R10 unique_id 修正：跨 hub 撞號** — 2026-05-24 — `manifest.json` version `20260523r5`
  - 動機：實機部署兩個 hub 後，HA log 跳出 `Platform lifesmart does not generate unique IDs. ID connectivity_0020 is already used`。原因：規範 §6.1 的 `me` 只在「同一個 hub 內」唯一；hub 自建的系統裝置（如 `V_SI / me=0020`）會在每個 hub 上重複出現，導致 R6 設計的 `<feature>_<me>` unique_id 跨 hub 撞號，第二個 hub 的 entity 被 HA 丟棄。
  - 影響範圍：所有走 R6 命名規範的 per-sub-device unique_id — `connectivity`、`signal`、`temp`、`battery`、`cover`、`remote`、`switch`。
  - 新模板：`<feature>_<agt>_<me>` 或 `<feature>_<agt>_<me>_<idx>`（switch）。`agt` 來自規範 §6.1 的 device 公共屬性，是 hub 全域唯一 ID，base64-ish 字串（如 `a3yaaabpagywrzazmdm3oq`），跨 hub 不會撞。
  - 修改的檔案：[binary_sensor.py](custom_components/lifesmart/binary_sensor.py)、[sensor.py](custom_components/lifesmart/sensor.py)（temp/battery/signal 三處）、[cover.py](custom_components/lifesmart/cover.py)、[switch.py](custom_components/lifesmart/switch.py)、[remote.py](custom_components/lifesmart/remote.py)（line 83 的遷移 helper 與 line 111 init 都改）。
  - `__init__.py` 新增 `_migrate_unique_ids(hass, entry, devices)` helper：
    - 在 `async_setup_entry` 走完 discovery、設好 `entry_data` 之後、`async_forward_entry_setups` 之前呼叫
    - 走 `er.async_get(hass).entities`，篩選屬於本 config_entry 的 entity
    - 解析 unique_id：`feature_<rest>`，若 `feature` 在白名單 (`_LEGACY_FEATURES`) 且 `rest` 的首段在 `me_to_agt` 字典裡，則重寫為 `feature_<agt>_<rest>`
    - 冪等：已遷移過的 unique_id（第二段是 agt，不是 me）會被偵測跳過 — 安全多次執行
  - 對單 hub 使用者的影響：entity_id 不變（`generate_entity_id` 已含 agt，與 unique_id 改動無關），unique_id 由 migration helper 就地改寫 → 使用者的自動化／儀錶板**完全不受影響**。
  - 對雙 hub 使用者的影響：第一次部署 R10 後，舊 hub 1 的 entities 被 migration 改名，hub 2 的 entities 用新格式註冊 — 之前 hub 2 被吞掉的 entity 重新出現（包含 `binary_sensor.v_si_a3yaaabdagctrzazmdm3oq_0020_connectivity`）。
  - 已知限制：`remote` entity_id 仍是 `remote.<slugify(name)>_<me>`（不走 generate_entity_id），如果兩個 hub 都有同名 remote 且同 me，entity_id 會 `_2` 加尾 — 此 R10 不處理（另外的 entity_id 命名問題，非 unique_id 問題）。✅ **R10-b 已解決**

- [x] **R10-b remote entity_id 也加 agt** — 2026-05-24 — `manifest.json` version `20260523r6`
  - 動機：R10 收尾時遺留的 entity_id 命名問題 — `remote` 平台 entity_id 走 `remote.<slugify(name)>_<me>`，沒 agt，雙 hub 撞號時 HA 會自動加 `_2` 尾碼。
  - [remote.py:81](custom_components/lifesmart/remote.py:81) `desired_object_id` 與 [line 116](custom_components/lifesmart/remote.py:116) `self.entity_id` 都改成 `<name_slug>_<agt>_<me>`。
  - 自動 in-place 改寫：[remote.py:80-87](custom_components/lifesmart/remote.py:80) 原本就有「desired entity_id 與既有不符就 rename」的 block — 改了 desired 模板後，這個 block 自動把舊 entity_id（無 agt）就地改成新格式（含 agt），不會建新 entity。
  - 對使用者影響：自動化／儀錶板裡硬編碼的 `remote.<name>_<me>` 會失效，要更新成 `remote.<name>_<agt>_<me>`（這是與 R10 不同的地方 — R10 entity_id 不變、R10-b entity_id 變）。
  - 唯一 entity_id 仍有問題的平台：**沒有了**。所有 7 個 sub-device 平台 (`switch` / `sensor.temp` / `sensor.battery` / `sensor.signal` / `binary_sensor.connectivity` / `cover` / `remote`) 都有 agt 在 entity_id 與 unique_id 中。

- [ ] **R8 Hub 層級功能盤點與規劃** — 2026-05-23（研究階段）
  - 動機：目前 integration 只暴露子裝置實體（switch/sensor/cover/remote）。LifeSmart Hub 自身的版本、重啟、場景、訊號等能力都沒接到 HA。
  - 規範來源：Local Interfaces §2 / §3.3.9 / §3.3.10 / §4 / §5；OpenDev 1.9 §2.3.4。

  **可暴露能力盤點：**
  | # | 規範 | 命令／事件 | 內容 | 已實作 | HA 對應 |
  |---|---|---|---|---|---|
  | 1 | LI §3.3.10 | `cfg:getver` | `ver` 韌體版本 / `osver` 系統版本 / `mgatype` 型號（LSJZX1K / LSSSMINIV1 / LSNAMIV1/3/4 / LSMGANAV1 / LSHI3518） | ❌ | 3× diagnostic sensor |
  | 2 | LI §3.3.10 | `cfg:reboot` | 重啟 hub | ❌ | `button`（`device_class=RESTART`） |
  | 3 | LI §3.3.10 | `cfg:reset` | 恢復出廠（毀滅性） | ❌ | service only（`confirmation: true`） |
  | 4 | LI §3.3.10 | `cfg:upgrade` | 韌體升級 | ❌ | `button` + 警示 |
  | 5 | LI §3.3.10 | `cfg:devname` | 設 hub／子裝置名稱（無 `me` = hub 本身） | ❌ | service |
  | 6 | LI §3.3.10 | `cfg:timezone` | 查／設時區 + DST | ❌ | sensor (查) + service (設) |
  | 7 | LI §3.3.10 | `cfg:notify` | 設定事件接收端 host/port | ✅ `api.configure_event_service` | 內部用，不需 entity |
  | 8 | LI §3.3.10 | `cfg:airctrl` | HVAC 面板搜尋 | ❌ | service（範圍受限） |
  | 9 | LI §3.3.9 | `rssi`（不帶 `me`） | hub 自身 noise / fromrssi / torssi **[未驗證]** | ❌ | 3× diagnostic sensor |
  | 10 | LI §5 | scene 查詢 + 觸發（`scene` / `groupirc` / `groupsw` / `grouphw` / `grouprgbw`） | hub 內定義場景 | ❌ | HA `scene` 平台 |
  | 11 | LI §4 | NOTIFY `chg.stat` | 子裝置上下線（1/0） | 部分 | per-device `binary_sensor`（`CONNECTIVITY`） |
  | 12 | LI §2 | UDP discovery（MOD/SN/NAME/VER） | hub 元資料 | ✅ config_flow | DeviceInfo 屬性 |
  | 13 | OD §2.3.4 | `cfg:net` + `cmd:getifn` | 網卡狀態 / IP / SSID / Gateway | ❌ | diagnostic sensor（**DEFED 機型限定**） |

  **分階段建議：**
  - **Phase 1（低風險高價值）：** A. `cfg:getver` → 3 個 diagnostic sensor；B. `cfg:reboot` → `button`（RESTART）；C. §5 場景 → HA `scene` 平台（先支援 `cls=scene`、`cls=groupirc`）
  - **Phase 2（中等）：** D. §4 NOTIFY → per-device `binary_sensor`（CONNECTIVITY）；E. hub `rssi`（需先實機驗證）；F. `cfg:timezone` sensor + service
  - **Phase 3（高風險／受限）：** G. `cfg:reset` / `cfg:upgrade` → service（confirmation 必須）；H. `cfg:net`（DEFED 限定，需先用 `cfg:getver` 判斷機型）

  **不建議實作：** `cfg:airctrl` 過於特殊（service 即可）；NOTIFY `add`/`del` 事件（應觸發 config_entry reload，不應做即時 entity 操作）。

  **已知風險／待驗證：**
  - `cfg:notify` 規範說每 300s 重設一次（LI §4 L1603），但目前 `api.configure_event_service` 只在啟動時呼叫 — 5 分鐘後可能失效。**需獨立查證是否已有定期 re-notify 機制**，否則為潛在 bug。
  - `rssi` 不帶 `me` 取 hub 自身 RSSI 是規範語意推論（原文 typo「If there is no is in me」），實作前必須先實機驗證。
  - `cfg:reboot` / `cfg:reset` 收到立刻執行，HA 端必須加 confirmation 保護。
  - scene `id` 格式為 `AI...` 字串（LI §5.1 L1719），不是數字。

- [x] **R9 Hub 層級 Phase 1（getver sensors + reboot button + scenes）** — 2026-05-23 — `manifest.json` version `20260523r4`
  - 範圍：R8 表格 Phase 1 三項一起做，因為共用 hub DeviceInfo 與 `hub_info` cache。
  - `api.py` 新增 4 個 helper：`get_hub_version` (cfg:getver SET)、`reboot_hub` (cfg:reboot SET)、`get_scene_list` (scene GET)、`trigger_scene` (doscene SET)。
  - `__init__.py` 在 `async_setup_entry` discovery 完成後追打一次 `cfg:getver`，回傳的 `ver` / `osver` / `mgatype` 存進 `entry_data["hub_info"]` — 所有 hub-level entity 都從這裡讀，不重複 query。失敗為非致命（hub entity 會顯示 None，子裝置功能照常）。
  - `const.py` — `PLATFORMS` 加入 `"button"`, `"scene"`；新增 `HUB_MODEL_NAMES` 字典（LI §3.3.10 L1561-1576 的 `mgatype` → 友善名稱對照）。
  - `sensor.py` — 新增 `LifeSmartHubInfoSensor` 類別 + 在 `async_setup_entry` 末尾無條件建立 3 個 instance：`firmware_version` / `os_version` / `model`。掛在合成的 hub DeviceInfo (`identifiers={(DOMAIN, f"hub_{host}")}`)；`EntityCategory.DIAGNOSTIC`；entity_id `sensor.lifesmart_hub_<slug>`（手寫，不走 `generate_entity_id`）。
  - `button.py` **NEW** — `LifeSmartHubRebootButton`，`ButtonDeviceClass.RESTART` + `EntityCategory.CONFIG`；`async_press` 呼叫 `api.reboot_hub`；entity_id `button.lifesmart_hub_reboot`；UDP 例外當作「已開始重啟」處理（hub ACK 後立刻斷線是預期行為）。
  - `scene.py` **NEW** — `LifeSmartScene`，`async_setup_entry` 跑 `api.get_scene_list`，遍歷回傳 list 為每個 `cls in ("scene", "groupirc")` 建一個 HA Scene；其他 cls（`groupsw`/`grouphw`/`grouprgbw` 帶 on/off + 顏色）INFO log 跳過、不建。unique_id `scene_<AI_id>`；entity_id `scene.lifesmart_<name_slug>_<id_tail>`；**不掛**在 hub device 下（HA scene 平台慣例）。
  - **意外發現**：原本以為 `cfg:notify` 重啟後失效是 bug，重讀 `__init__.py:80-87` 才知道 `_refresh_notify` 已經 90s 跑一次了 — 不是 bug，CLAUDE.md / PROGRESS.md 之前的警告是錯的，順手修正。
  - 已知限制：(1) `hub_info` 是 setup 時 single-shot 取，hub 韌體更新後 sensor 不會自動刷新（除非 reload integration）；(2) Scene `args.args.type=128` 是依規範範例 L1077 寫法，未對其他 cls 驗證過；(3) Reboot 後 `__init__.py` 沒重跑 discovery，新的 hub_info 要等使用者手動 reload。

- [x] **R8-b 子裝置連線狀態 binary_sensor（stat push + 輪詢）** — 2026-05-23 — `manifest.json` version `20260523r2`
  - 範圍：R8 表格第 11 項（Phase 2 起始項）— 為每個有 `stat` 的子裝置建一個 CONNECTIVITY binary_sensor。
  - 規範來源：LI §6.1（`stat`：1=online、0=offline）+ LI §4（NOTIFY 事件含 `stat` 用於上下線通知）。
  - 新檔：`custom_components/lifesmart/binary_sensor.py`（`LifeSmartConnectivitySensor`）。
  - `const.py` — `PLATFORMS` 加入 `"binary_sensor"`，`async_forward_entry_setups` 自動承接。
  - `api.py` — `_extract_state_changes` 擴充：原本只處理 `chg[k]` 為 `dict` 且帶 `.v` 的 channel value；現在 `k == "stat"` 且為 scalar 也 emit `(me, "stat", value)`，當虛擬 idx 派發給 state_listeners。
  - `LifeSmartConnectivitySensor` 設計：(1) `register_state_listener(me, "stat", cb)` 接 push 即時更新；(2) 15 min 後備輪詢 `ep` GET 取 `msg.stat` — 防止 push 漏失。
  - 屬性：`BinarySensorDeviceClass.CONNECTIVITY` + `EntityCategory.DIAGNOSTIC`；`_attr_name = "Connectivity"`；unique_id `connectivity_<me>`；entity_id `binary_sensor.<devtype>_<agt>_<me>_connectivity`。
  - 已知不足：(1) 規範 §4 還有 `add`/`del` 事件（裝置新增刪除），目前未觸發 config_entry reload；(2) 沒有對首次 setup 時離線裝置的特別處理（會建一個 `is_on=False` 的 entity）。
  - **未分類裝置觀察（2026-05-23）：** 實機環境下發現 `devtype=V_SI`、`me=0020` 的裝置，產出 `binary_sensor.v_si_<agt>_0020_connectivity`。`V_SI` 不在 LI v1.10 或 OD 1.9 規範中，疑似為 hub 自建的虛擬系統裝置（與 §6.8/§6.9 的 `V_AIR_P` / `V_FRESH_P` / `V_DLT_645_P` / `V_IND_S` 同屬 `V_*` 前綴家族）。**決策：保持現狀不過濾、不重命名** — 因為 `V_SI` 既有 `stat` 屬性、R8-b 邏輯就照規範把它當一般 sub-device 處理。若未來需要分類，可在 binary_sensor.py / sensor.py 加 `devtype.startswith("V_")` 條件做 INFO log dump，從 firmware 回的 `name` / `data` / `fulltype` 反推用途。

- [x] **R8-a 子裝置訊號強度 sensor（lDbm 走全裝置）** — 2026-05-23 — `manifest.json` version `20260523r1`
  - 範圍：R8 表格新增第 14 項，獨立於 hub 三項 Phase 1（getver / reboot / scenes）之外先行。
  - 規範來源：LI §6.1 Common Attributes（[L1917-1923](Docs/Local%20Interfaces%20of%20LifeSmart%20Smart%20Station_20230926.md#L1917)）— 每個 sub-device 在 `eps` 回應頂層含 `lDbm`（dBm 數值，device→hub 方向訊號強度），電池與非電池裝置皆有。
  - `sensor.py` 新增 `LifeSmartSignalSensor`：`SensorDeviceClass.SIGNAL_STRENGTH` + `SensorStateClass.MEASUREMENT` + `EntityCategory.DIAGNOSTIC` + 單位 `SIGNAL_STRENGTH_DECIBELS_MILLIWATT`。
  - `__init__` 用 `idx=None` 傳給 base class（不註冊 state listener，因為 `lDbm` 不在 `data[idx]` 內）；entity_id 用虛擬 idx `"signal"` 走 `generate_entity_id()` → `sensor.<devtype>_<agt>_<me>_signal`。
  - `_async_update` 走 `ep` GET 取 `response["msg"]["lDbm"]`，遵守現有 15 分鐘輪詢節奏。
  - `async_setup_entry` 新增獨立 `if "lDbm" in device` 區塊（**不是 elif**），與既有 devtype-specific 分支並存 — 例如 `SL_NATURE` 同時建溫度與訊號 sensor。
  - 為何不走 `rssi` 命令？(1) 電池裝置會回 code 102；(2) 需額外 UDP round-trip；(3) 單位要自己換算 `(RSSI/2)-134`。`lDbm` 在 `eps` 已含、直接是 dBm、所有裝置都能用。
  - 已知限制：lDbm 變動無 push 通道（規範未說 NOTIFY 會回報 lDbm），純 15 分鐘輪詢；如要更即時須改用 `rssi` 命令做為對 AC-powered 裝置的額外路徑（暫不做）。
  - **`stat` per-device CONNECTIVITY binary_sensor 仍未實作**（需新增 binary_sensor 平台）— 留在 R8 Phase 2。

---

### R12 P3 全部修 — 2026-05-24 — `manifest.json` version `20260524r0`

技術債 P3 七項全處理。

- [x] **D11 收斂 `except Exception`**：24 處 → 2 處（保留 `api.py` 的 listener isolation，含 `# noqa: BLE001` 註解）。其他改成 `(asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError)` 或 `(struct.error, UnicodeDecodeError, json.JSONDecodeError)` 等具體型別。
- [x] **D12 pytest 基礎 + 3 個關鍵函式測試**：建立 `tests/`、`conftest.py`（HA stubs + voluptuous stub + update_coordinator stub）、3 個 test 檔（21 個 test 全綠）：
  - `test_generate_entity_id.py` — 7 個 case（含 lls_ revert 保險、R10 agt 跨 hub 保險）
  - `test_extract_state_changes.py` — 7 個 case（含 R8-b 的 stat scalar dispatch 保險）
  - `test_migrate_unique_ids.py` — 7 個 case（含 R10 idempotency、cross-entry isolation）
- [x] **D13 zh-Hant + zh-Hans 翻譯**：擴充 `translations/`；en.json 也補上 issues 段（給 D17 用）。
- [x] **D14 async_migrate_entry**：`ConfigFlow.VERSION` 1→2；新增 `async_migrate_entry` helper 在版本升級時自動跑 R10 遷移；`async_setup_entry` 內保留 defensive idempotent 重跑（首次 discovery 失敗時的補救）。
- [x] **D15 DataUpdateCoordinator（partial）**：
  - 新建 `coordinator.py` `LifeSmartCoordinator`，週期性跑 `eps` 全量取所有裝置（取代 per-entity polling）。
  - `__init__.py` setup 時實例化 coordinator，用 `async_set_updated_data` 餵入 discovery 結果作為種子。
  - `sensor.py` 三個輪詢 sensor (Temperature / Battery / Signal) 重構：base class 接受 coordinator 參數，移除 `async_track_time_interval`，加 `_handle_coordinator_update` callback。對 N 個 sensor 的 hub，輪詢請求從 N 條降為 1 條（eps）。
  - Push (NOTIFY) 機制保留不動；coordinator 與 state_listener 並行不衝突。
  - **未完成**（D15 follow-up，留作 R13）：`binary_sensor.py` (connectivity) 與 `cover.py` 仍是 per-entity polling。Hub-level sensor (LifeSmartHubInfoSensor) 不需要 coordinator（read-only 從 `hub_info` cache 拿）。
- [x] **D16 diagnostics.py 平台**：實作 `async_get_config_entry_diagnostics` 與 `async_get_device_diagnostics`；輸出 entry config（token 等敏感欄位 redact）、`hub_info`、`devtype_counts` 統計（可快速看出 V_SI 這種未文件化 devtype）、完整 devices 載荷。使用者從 HA UI「下載診斷」即可拿到，bug report 不再需要 grep log。
- [x] **D17 repair / issue 框架**：`cfg:getver` 失敗時透過 `ir.async_create_issue` 建 `hub_version_unknown` 問題，HA UI 直接可見；成功時自動清除。translation key 也加進 en/zh-Hant/zh-Hans。

統計：~620 行新增／修改、3 個新檔（`coordinator.py`、`diagnostics.py`、`tests/*`）、5 個翻譯／manifest／文件變更。

### 技術債盤點（R11，2026-05-24）

**現狀快照** — 22 項 backlog，依「確定性 × 嚴重性」分 5 等級。CLAUDE.md「技術債清單」段保留關鍵子集，這裡是完整單。掃描方法：grep 源碼 TODO/FIXME（0 命中）+ 中文 debt 標記 + PROGRESS.md 已記限制 + 結構性審查（例外處理、測試、i18n、coordinator、diagnostics）。

#### 🔴 P0 — 規範推論未實機驗證，可能 silently 錯誤
- **D1 `cover.py` PORT_STATE = "P1" 通道是推測** — [cover.py:17](custom_components/lifesmart/cover.py:17)；規範 §6.9.1 P1 為配置暫存器，真實狀態通道不明；窗簾位置回報可能完全錯誤；繼承自原 L3 條目（自 2026-05-16 開放）
- **D2 Scene `args.args.type=128` 是硬抄規範範例** — [api.py:186-196](custom_components/lifesmart/api.py:186)；§5.2 對 `cls=scene` / `groupirc` 標 N/A 但例子用 128（0x80=off）；可能觸發失敗但 hub 仍回 code=0
- **D3 `rssi` 不帶 `me` 取 hub 訊號是語意推論** — 規範原文 typo「If there is no is in me」；尚未實作但已計畫（R8 Phase 2），實作前必先實機驗證

#### 🟠 P1 — 既知設計妥協、操作體驗有瑕疵
- **D4 `hub_info` setup-time single-shot，韌體升級後不刷新** — [__init__.py:73-89](custom_components/lifesmart/__init__.py:73)；建議：24h 輪詢 `cfg:getver` 或 reboot button 完成後排程 refresh
- **D5 Reboot 後 `__init__.py` 沒重跑 discovery** — [button.py:78-91](custom_components/lifesmart/button.py:78)；建議：reboot 成功後 60-120s 後 `async_reload`
- **D6 NOTIFY `add` / `del` 事件未處理** — [api.py:229-259](custom_components/lifesmart/api.py:229)；§4 明文 NOTIFY 送子裝置新增/刪除，目前忽略 → 使用者新配對裝置不會自動出現；建議：`_report_listeners` 加 listener 觸發 `async_reload`
- **D7 首次 setup 看到離線裝置直接建 `is_on=False` entity** — [binary_sensor.py:63-67](custom_components/lifesmart/binary_sensor.py:63)；建議：初值用 `unknown` 而非 `False`

#### 🟡 P2 — R8 Phase 2/3 未實作的規範命令／裝置型號
- **D8 規範命令未實作**：`cfg:timezone`（Phase 2）、hub `rssi`（Phase 2，先 D3）、`cfg:reset` / `cfg:upgrade` / `cfg:devname`（Phase 3，皆需 service + confirmation）、`cfg:net getifn`（Phase 3，DEFED 限定）、`cfg:airctrl`（Phase 3，HVAC 限定）
- **D9 子裝置型號／通道未實作**：
  - CUBE Clicker `SL_SC_BB` / `SL_SC_BB_V2`（§6.3.6 / §6.3.7）的 V 電池通道
  - `SL_MC_ND*` 的 B1/B2/B3 button 通道（§6.3.5）— 建議用 HA `event` platform（2024.6+）
  - `SL_MC_ND*` 的 L1/L2/L3 switch 通道（§6.3.5）— [switch.py:18-30 SUPPORTED_SWITCH_TYPES](custom_components/lifesmart/switch.py:18) 未列
  - Scene `cls in (groupsw, grouphw, grouprgbw)`（§5.2 帶 on/off+顏色狀態，[scene.py:25](custom_components/lifesmart/scene.py:25) 目前跳過）
- **D10 `valts` device 屬性未使用**（§6.1「最後屬性變動時戳」），可作為 sensor extra_state_attribute

#### 🟢 P3 — 代碼品質債
- **D11 全專案 24 處 `except Exception` 通吃** — 9 個檔案；建議：收斂為具體型別 (`asyncio.TimeoutError`, `OSError`, `json.JSONDecodeError`, `KeyError`)
- **D12 完全沒有單元測試** — `find . -name "test_*.py"` 0 命中；起步建議：`test__extract_state_changes()`、`test__migrate_unique_ids()`、`test_generate_entity_id()`
- **D13 translations 只有 en.json** — 缺 `zh-Hant.json`（主要使用者語言）、`zh-Hans.json`、`ja.json` 等
- **D14 ConfigFlow `VERSION = 1`，無 `async_migrate_entry`** — [config_flow.py:49](custom_components/lifesmart/config_flow.py:49)；R10 走土法遷移，沒走 HA 標準路徑；未來改 entry data 結構時要補
- **D15 沒用 `DataUpdateCoordinator`** — CLAUDE.md「規範文件」段明文要求；現狀：每個 sensor 各自 `async_track_time_interval` → 同 hub 重複請求；改用 coordinator 後請求量除以 N
- **D16 沒有 diagnostics 平台** — HA 標準 `diagnostics.py` 讓使用者下載 hub_info / devices 全集；目前 debug `V_SI` 那次要新建 log 字串才能撈；建議：實作 `async_get_config_entry_diagnostics`
- **D17 沒有 repair / issue 報告** — `cfg:notify` 失敗、hub 持續 timeout 等情境只 log warning；HA 有 `ir.async_create_issue` 可建前端可見的修復項目

#### 🔵 P4 — 邊角
- **D18 `api.py send_command` 無重試** — [api.py:140](custom_components/lifesmart/api.py:140)；UDP 丟包單次就失敗；對 CMD_SET 控制命令影響較大
- **D19 `services.yaml` 只有 `send_keys`** — 缺 `trigger_scene` / `refresh_hub_info` / `reboot_hub`（service 形式可帶 confirmation）
- **D20 R5 `lls_` 前綴的歷史 entity 不會被 `_migrate_unique_ids` 處理** — R10 邏輯只認 R6 後的 `<feature>_<me>` 格式；影響極小（R5→R6 revert 時已要求使用者重加整合）
- **D21 Hub DeviceInfo 用 host IP 作 identifier，IP 變更會孤兒** — CLAUDE.md「Hub-level entity 組織慣例」已記註；未來改用 §2 discovery 抓 SN 才穩
- **D22 子裝置 DeviceInfo 沒加 `via_device=(DOMAIN, hub_identifier)`** — 5 個平台檔需一次性加；UI 上 hub→sub-devices 階層展示缺失；**「投資報酬最高的小改」**

#### 建議的下手順序（ROI 排序）
1. D2 Scene type=128 實測（部署 Phase 1 順手）
2. D1 cover P1 通道實測（懸了最久）
3. D13 zh-Hant 翻譯（小工程、馬上受益）
4. D22 sub-device via_device（UI 直接整潔）
5. D16 diagnostics 平台（下次 bug 報告省事）
6. D6 NOTIFY add/del 處理（自動感知新裝置）
7. D15 DataUpdateCoordinator 重構（HA 2026.5 規範相容性）

#### 統計
| 等級 | 項目數 | 性質 |
|---|---|---|
| 🔴 P0 | 3 | 規範推論未驗證 |
| 🟠 P1 | 4 | 設計妥協 |
| 🟡 P2 | 3 | 規範覆蓋缺漏（R8 Phase 2/3） |
| 🟢 P3 | 7 | 代碼品質 |
| 🔵 P4 | 5 | 邊角細節 |
| **合計** | **22** | |

---

### 累計統計（含第四輪）

| 嚴重程度 | 數量 | 已修復 |
|---------|------|--------|
| 嚴重 Bug（C+R） | 7 | 7 |
| 邏輯 Bug（L+R） | 13 | 12 |
| 警告（W+R） | 18 | 18 |
| **合計** | **38** | **37** |

**剩餘 1 項：**
- L3：P1 狀態通道未驗證（需實機測試）

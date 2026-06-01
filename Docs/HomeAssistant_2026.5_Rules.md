# Home Assistant 2026.5.0 整合開發規範摘要

本文件記錄本次代碼審查中確認的 HA 2026.5 規範要點，供後續修復作業參考。

---

## 1. Manifest（`manifest.json`）

- `domain` 必須與資料夾名稱完全相符（區分大小寫），否則 HA 拒絕載入整合
- `iot_class` 取代已棄用的 `CONNECTION_CLASS`；local push 整合應設為 `"local_push"`
- `"options": true` 表示支援選項流程，必須在 `config_flow.py` 實作 `async_step_options`；宣告但未實作會讓 UI 顯示無法使用的選項按鈕
- `"config_flow": true` 必須搭配 `ConfigFlow` 實作

---

## 2. Config Flow（`config_flow.py`）

- **已移除**：`@config_entries.HANDLERS.register(DOMAIN)` — 不再需要此裝飾器，直接繼承 `ConfigFlow` 即可
- **已棄用**：`CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH` — 改用 manifest 的 `iot_class`
- 必須實作 `async_step_user`（初始設定）
- 建議實作 `async_step_reconfigure`（認證過期重設）
- 若 manifest 宣告 `options: true`，必須實作 `async_step_options`
- 翻譯資料夾：`translations/`（複數），HA 忽略 `translation/`（單數）
- `translations/en.json` 需包含所有已實作 step 的翻譯鍵（`user`、`reconfigure`、`options` 等）

---

## 3. 全面非同步化（Async-First）

- 禁止使用阻塞 I/O（`requests`、`socket.recv` 等）於 event loop 中
- 網路請求必須使用 `aiohttp`，透過 `async_get_clientsession(hass)` 取得 session
- **`hass.async_add_executor_job`**：只能包裹同步阻塞函式；coroutine 不可傳入，否則只會建立 coroutine 物件而不執行
- asyncio UDP：使用 `loop.create_datagram_endpoint` 搭配 `asyncio.DatagramProtocol`

---

## 4. 資料更新協調器（DataUpdateCoordinator）

- 外部 API 輪詢必須透過 `DataUpdateCoordinator` 統一管理
- 實作 `_async_update_data` 方法，HA 負責排程與錯誤處理
- 同一 config entry 下的所有實體共用同一個 coordinator 實例，避免重複請求
- push 架構（`iot_class: local_push`）可不主動輪詢，改由 UDP NOTIFY 推播驅動更新

---

## 5. 實體狀態更新

- **`async_write_ha_state()`**：直接更新 HA 狀態機，不觸發 poll；push 實體應使用此方法
- **`async_update_ha_state()`**：觸發 poll（呼叫 `async_update`），會產生不必要的請求；`_attr_should_poll = False` 的實體不應呼叫此方法
- 設定 `_attr_should_poll = False` 後，HA 不會主動輪詢；所有狀態更新必須由推播事件觸發，並呼叫 `async_write_ha_state()`

---

## 6. 實體命名（Entity Naming）

- **2026.5 規範**：實體名稱（`_attr_name`）不得包含裝置名稱（Device Name）
- HA 前端 UI 會自動將 DeviceInfo 的裝置名稱與實體名稱組合顯示
- `DeviceInfo.name` 應設為裝置層級名稱（例：`"客廳冷氣"`）
- `_attr_name` 應設為功能描述（例：`"溫度"`），不含裝置名稱
- 違反此規範會導致 HA 發出警告並可能在未來版本強制修正

---

## 7. 型別提示（Type Hinting）

- 所有函式與方法必須包含完整型別標註
- `Optional[callable]` 錯誤：`callable` 是內建函式非型別，應改為 `Optional[Callable[[], None]]`
- 需從 `typing` 匯入：`Optional`, `List`, `Dict`, `Any`, `Callable`, `Tuple` 等
- 目標：能通過 `mypy --strict` 檢查

---

## 8. 日誌（Logging）

- 避免在 logging 呼叫中使用 f-string：`_LOGGER.debug(f"val={val}")` ← 錯誤
- 正確方式：`_LOGGER.debug("val=%s", val)` — 讓 logger 懶惰格式化，log level 關閉時不計算字串

---

## 9. 服務定義（`services.yaml`）

- 每個服務的 `fields` 應包含 `selector` 區塊，以啟用 HA UI 的表單輸入
- 範例：
  ```yaml
  send_keys:
    fields:
      remote_id:
        selector:
          text:
      keys:
        selector:
          text:
  ```

---

## 10. 其他

- `generate_entity_id` 類型的函式中，索引值判斷應用 `if idx is not None:` 而非 `if idx:`，避免 `0` 或空字串被誤判為 falsy
- 不應將真實憑證（token、密碼）作為 config flow 欄位的預設值
- `coordinator.py` 若未被 `__init__.py` 匯入，整個檔案為死程式碼，應刪除或重新整合

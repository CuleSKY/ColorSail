# /embed/servers 宓屽叆璇存槑

璇ラ〉闈㈢敤浜庡湪妗岄潰绔垨澶栭儴瀹瑰櫒涓祵鍏?CS2ZE 鏈嶅姟鍣ㄥ垪琛紝浠呮覆鏌撴湇鍔″櫒鍒楄〃鍖哄煙锛屼笉鍖呭惈涓荤珯鐨勪晶杈规爮/澶撮儴銆?

## URL 鍙傛暟
- `client`锛氬鎴风鏍囪瘑锛堢ず渚嬶細`tauri`锛夈€?
- `nonce`锛氫竴娆℃€ч殢鏈哄€硷紝鐢ㄤ簬 postMessage 鏍￠獙锛堢己澶辨椂涓嶄細鍚戝涓诲彂閫佹秷鎭級銆?
- `theme`锛歚light` 鎴?`dark`锛岀敤浜庢寚瀹氫富棰樸€?
- `lang`锛歚zh-CN`銆乣zh-TW`銆乣en` 绛夎瑷€鏍囪瘑銆?
- `tab`锛氳鍥炬爣璇嗭紙`servers` / `map_sub` / `stats` / `feedback`锛夈€?
- `dense`锛歚1` / `true` / `yes` 鏃跺惎鐢ㄧ揣鍑戝竷灞€銆?

绀轰緥锛?
```
/embed/servers?client=tauri&nonce=abc123&theme=dark&lang=zh-CN&tab=servers&dense=1
```

## postMessage 鍗忚
宓屽叆妯″紡涓嬶紝椤甸潰浼氬悜 `https://example.com` 鍙戦€佹秷鎭紝缁撴瀯濡備笅锛?
```json
{
  "type": "CS2ZE_READY | CS2ZE_JOIN | CS2ZE_COPY | CS2ZE_SUBSCRIBE_MAP",
  "v": 1,
  "nonce": "鏉ヨ嚜 URL 鐨?nonce",
  "payload": {}
}
```

### 娑堟伅绫诲瀷涓?payload
- `CS2ZE_READY`锛歚{ "features": ["join","copy","subscribe_map"] }`
- `CS2ZE_JOIN`锛歚{ "ip": "1.2.3.4", "port": 27015, "name": "Server Name" }`
- `CS2ZE_COPY`锛歚{ "text": "connect ip:port", "kind": "connect" }`
- `CS2ZE_SUBSCRIBE_MAP`锛歚{ "map": "ze_xxx" }`


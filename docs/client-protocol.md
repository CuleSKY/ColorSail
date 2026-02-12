# CS2ZE Web 鈫?Client 鍗忚锛坴1锛?

鏈崗璁敤浜?`/embed/servers` 宓屽叆椤典笌妗岄潰瀹㈡埛绔箣闂寸殑娑堟伅浜や簰銆傚祵鍏ラ〉浠呴€氳繃 `postMessage` 涓庡鎴风閫氫俊锛屼笉鐩存帴瑙﹀彂绯荤粺鑳藉姏銆?

## 鐗堟湰
- `v`: 1

## 閫氱敤娑堟伅缁撴瀯
```json
{
  "type": "CS2ZE_READY | CS2ZE_JOIN | CS2ZE_COPY | CS2ZE_SUBSCRIBE_MAP",
  "v": 1,
  "nonce": "鏉ヨ嚜 URL 鐨?nonce",
  "payload": {}
}
```

## 鍙戦€佺洰鏍?
- `targetOrigin`: `https://example.com`锛堢姝娇鐢?`*`锛?

## 娑堟伅绫诲瀷涓?payload
### CS2ZE_READY
```json
{
  "features": ["join", "copy", "subscribe_map"]
}
```

### CS2ZE_JOIN
```json
{
  "ip": "1.2.3.4",
  "port": 27015,
  "name": "Server Name"
}
```

### CS2ZE_COPY
```json
{
  "text": "connect 1.2.3.4:27015",
  "kind": "connect"
}
```

### CS2ZE_SUBSCRIBE_MAP
```json
{
  "map": "ze_example_map"
}
```

## 闄嶇骇琛屼负锛堟櫘閫氭祻瑙堝櫒锛?
- 鑻ョ己灏?`nonce`锛屽祵鍏ラ〉涓嶄細鍙戦€佹秷鎭紝Join/Copy 浼氶檷绾т负澶嶅埗 `connect` 鍛戒护銆?
- 闈?`client=tauri` 鍦烘櫙涓嬶紝椤甸潰浠嶅彲姝ｅ父娴忚鏈嶅姟鍣ㄥ垪琛紝浣嗕笉浼氳Е鍙戞湰鍦拌兘鍔涖€?


# CS2ZE Web ↔ Client 协议（v1）

本协议用于 `/embed/servers` 嵌入页与桌面客户端之间的消息交互。嵌入页仅通过 `postMessage` 与客户端通信，不直接触发系统能力。

## 版本
- `v`: 1

## 通用消息结构
```json
{
  "type": "CS2ZE_READY | CS2ZE_JOIN | CS2ZE_COPY | CS2ZE_SUBSCRIBE_MAP",
  "v": 1,
  "nonce": "来自 URL 的 nonce",
  "payload": {}
}
```

## 发送目标
- `targetOrigin`: `https://www.cs2ze.org`（禁止使用 `*`）

## 消息类型与 payload
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

## 降级行为（普通浏览器）
- 若缺少 `nonce`，嵌入页不会发送消息，Join/Copy 会降级为复制 `connect` 命令。
- 非 `client=tauri` 场景下，页面仍可正常浏览服务器列表，但不会触发本地能力。

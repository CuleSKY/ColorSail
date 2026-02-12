# `/embed/servers` Integration Guide

The `/embed/servers` page is designed for desktop-container embedding and external host integration.
It renders only the server-list experience (not the full website shell).

## URL query parameters

- `client`: host client identifier (example: `tauri`)
- `nonce`: one-time random token used for `postMessage` validation
- `theme`: `light` or `dark`
- `lang`: language code such as `en`, `zh-CN`, `zh-TW`
- `tab`: initial view (`servers`, `map_sub`, `stats`, `feedback`)
- `dense`: compact mode (`1`, `true`, `yes`)

Example:

```text
/embed/servers?client=tauri&nonce=abc123&theme=dark&lang=en&tab=servers&dense=1
```

## postMessage contract

In embed mode, the page posts messages to `https://example.com` using:

```json
{
  "type": "CS2ZE_READY | CS2ZE_JOIN | CS2ZE_COPY | CS2ZE_SUBSCRIBE_MAP",
  "v": 1,
  "nonce": "value from URL query nonce",
  "payload": {}
}
```

Message payloads:

- `CS2ZE_READY`: `{ "features": ["join", "copy", "subscribe_map"] }`
- `CS2ZE_JOIN`: `{ "ip": "1.2.3.4", "port": 27015, "name": "Server Name" }`
- `CS2ZE_COPY`: `{ "text": "connect ip:port", "kind": "connect" }`
- `CS2ZE_SUBSCRIBE_MAP`: `{ "map": "ze_xxx" }`

## Security requirements

- Always validate `origin` and `nonce` on both sides.
- Never use wildcard target origins.
- Keep sensitive host features gated by explicit client checks.

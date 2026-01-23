import a2s


def query_a2s(ip, port, timeout=1.5):
    try:
        info = a2s.info((ip, int(port)), timeout=timeout)
    except Exception:
        return None
    return {
        "name": getattr(info, 'server_name', None) or getattr(info, 'name', None),
        "players": getattr(info, 'player_count', None),
        "max_players": getattr(info, 'max_players', None)
    }

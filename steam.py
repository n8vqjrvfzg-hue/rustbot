"""Клиент Steam Web API: часы в Rust, инвентарь (скины) и список DLC."""
import asyncio
import logging
import random
import re

import aiohttp

import config

log = logging.getLogger(__name__)

RUST_APPID = 252490
API = "https://api.steampowered.com"


class SteamError(Exception):
    """text: 'private' | 'rate' | 'network' | 'http'"""


async def _get_json(url: str, params: dict | None = None):
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 429:
                    raise SteamError("rate")
                if resp.status in (401, 403):
                    raise SteamError("private")
                if resp.status != 200:
                    raise SteamError(f"http {resp.status}")
                return await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        raise SteamError("network") from e


def parse_steam_input(text: str):
    """Ссылка / SteamID64 / короткое имя -> ('id', value) | ('vanity', value) | None."""
    t = text.strip()
    m = re.search(r"steamcommunity\.com/profiles/(\d{17})", t)
    if m:
        return "id", m.group(1)
    m = re.search(r"steamcommunity\.com/id/([A-Za-z0-9_\-]+)", t)
    if m:
        return "vanity", m.group(1)
    if re.fullmatch(r"\d{17}", t):
        return "id", t
    if re.fullmatch(r"[A-Za-z0-9_\-]{2,32}", t):
        return "vanity", t
    return None


def make_code() -> str:
    return f"FLZ-{random.randint(1000, 9999)}"


async def resolve_vanity(vanity: str) -> str | None:
    data = await _get_json(
        f"{API}/ISteamUser/ResolveVanityURL/v1/", {"key": config.STEAM_API_KEY, "vanityurl": vanity}
    )
    resp = data.get("response", {})
    return resp.get("steamid") if resp.get("success") == 1 else None


async def get_player(steamid: str) -> dict | None:
    data = await _get_json(
        f"{API}/ISteamUser/GetPlayerSummaries/v2/", {"key": config.STEAM_API_KEY, "steamids": steamid}
    )
    players = data.get("response", {}).get("players", [])
    return players[0] if players else None


async def get_rust_hours(steamid: str) -> int | None:
    """Часы в Rust или None, если Steam их не отдаёт (скрыты «Данные об играх»)."""
    data = await _get_json(
        f"{API}/IPlayerService/GetOwnedGames/v1/",
        {
            "key": config.STEAM_API_KEY,
            "steamid": steamid,
            "include_played_free_games": 1,
            "appids_filter[0]": RUST_APPID,
        },
    )
    games = data.get("response", {}).get("games")
    if not games:
        return None
    for g in games:
        if g.get("appid") == RUST_APPID:
            return int(g.get("playtime_forever", 0)) // 60
    return None


async def get_inventory(steamid: str) -> dict:
    """Скины Rust из публичного инвентаря Steam. Бросает SteamError('private'), если инвентарь закрыт."""
    url = f"https://steamcommunity.com/inventory/{steamid}/{RUST_APPID}/2"
    total = 0
    classes: set = set()
    marketable_classes: set = set()
    marketable_count = 0
    start = None
    for _ in range(5):  # не больше 5 страниц по 2000 предметов
        params = {"l": "russian", "count": 2000}
        if start:
            params["start_assetid"] = start
        data = await _get_json(url, params)
        if not data or not data.get("success", 1):
            raise SteamError("private")
        descriptions = {d["classid"]: d for d in data.get("descriptions", [])}
        for a in data.get("assets", []):
            amount = int(a.get("amount", 1))
            total += amount
            classes.add(a["classid"])
            if descriptions.get(a["classid"], {}).get("marketable") == 1:
                marketable_count += amount
                marketable_classes.add(a["classid"])
        if data.get("more_items") and data.get("last_assetid"):
            start = data["last_assetid"]
            await asyncio.sleep(1.5)
        else:
            break
    return {"total": total, "unique": len(classes), "marketable": marketable_count}


async def get_dlc_list() -> list[tuple[int, str]]:
    """Список DLC Rust из магазина Steam: [(appid, название)]."""
    store = "https://store.steampowered.com/api/appdetails"
    data = await _get_json(store, {"appids": RUST_APPID, "l": "russian"})
    info = data.get(str(RUST_APPID), {})
    if not info.get("success"):
        raise SteamError("http")
    result = []
    for appid in info["data"].get("dlc", [])[:30]:
        await asyncio.sleep(0.4)
        try:
            d = await _get_json(store, {"appids": appid, "l": "russian", "filters": "basic"})
        except SteamError:
            continue
        item = d.get(str(appid), {})
        if item.get("success"):
            result.append((int(appid), item["data"]["name"]))
    if not result:
        raise SteamError("http")
    return result

# -*- coding: utf-8 -*-
"""
实时赛事数据模块 (football-data.org)
======================================

用 Python 标准库 urllib 抓取真实赛程与赛果, 无需第三方依赖。
数据源: https://www.football-data.org  (免费 token 注册: /client/register)

主要能力:
    - 拉取指定赛事 (默认 2026 世界杯 WC) 的全部比赛
    - 拆分为「即将进行」与「已结束」两类
    - 已结束比赛可转成校准用的比分记录 (配合 calibrate_ratings 使用)
    - 把 API 的英文/三字母队名映射为中文队名

Token 来源优先级: 显式传入 > 环境变量 FOOTBALL_DATA_TOKEN > config.json
"""

import json
import os

try:
    from urllib.request import Request, urlopen
    from urllib.parse import urlencode
    from urllib.error import HTTPError, URLError
except ImportError:  # Python 2 兜底 (基本用不到)
    from urllib2 import Request, urlopen, HTTPError, URLError
    from urllib import urlencode

API_BASE = "https://api.football-data.org/v4"
CONFIG_FILE = "config.json"
DEFAULT_RATING = 1700.0          # 未收录球队的默认评分
DEFAULT_COMPETITION = "WC"       # 世界杯

# football-data 三字母代码(FIFA) -> 中文队名
TLA_TO_ZH = {
    "ARG": "阿根廷", "FRA": "法国", "BRA": "巴西", "ENG": "英格兰",
    "ESP": "西班牙", "POR": "葡萄牙", "NED": "荷兰", "BEL": "比利时",
    "GER": "德国", "CRO": "克罗地亚", "ITA": "意大利", "URU": "乌拉圭",
    "MAR": "摩洛哥", "COL": "哥伦比亚", "MEX": "墨西哥", "USA": "美国",
    "SUI": "瑞士", "SEN": "塞内加尔", "DEN": "丹麦", "JPN": "日本",
    "KOR": "韩国", "AUS": "澳大利亚", "POL": "波兰", "ECU": "厄瓜多尔",
    "KSA": "沙特阿拉伯", "SAU": "沙特阿拉伯", "IRN": "伊朗", "GHA": "加纳",
    "CMR": "喀麦隆", "CAN": "加拿大", "QAT": "卡塔尔", "TUN": "突尼斯",
    "CHN": "中国",
    # 2026 世界杯可能参赛的其他球队 (无评分时用默认值)
    "AUT": "奥地利", "HUN": "匈牙利", "SRB": "塞尔维亚", "TUR": "土耳其",
    "WAL": "威尔士", "SCO": "苏格兰", "NOR": "挪威", "SWE": "瑞典",
    "UKR": "乌克兰", "CZE": "捷克", "GRE": "希腊", "NGA": "尼日利亚",
    "EGY": "埃及", "ALG": "阿尔及利亚", "CIV": "科特迪瓦", "MLI": "马里",
    "RSA": "南非", "CRC": "哥斯达黎加", "PAN": "巴拿马", "PAR": "巴拉圭",
    "PER": "秘鲁", "CHI": "智利", "VEN": "委内瑞拉", "NZL": "新西兰",
    "IRQ": "伊拉克", "UAE": "阿联酋", "UZB": "乌兹别克斯坦", "JOR": "约旦",
    "OMA": "阿曼", "BHR": "巴林",
}


class LiveDataError(Exception):
    """联网/接口相关错误, 便于界面统一提示。"""
    pass


# ---------------------------------------------------------------------------
# 配置与 token
# ---------------------------------------------------------------------------
def load_config(path=CONFIG_FILE):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(cfg, path=CONFIG_FILE):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_token(explicit=None, path=CONFIG_FILE):
    """按 显式 > 环境变量 > 配置文件 的顺序获取 API token。"""
    if explicit:
        return explicit.strip()
    env = os.environ.get("FOOTBALL_DATA_TOKEN")
    if env:
        return env.strip()
    return str(load_config(path).get("football_data_token", "")).strip()


# ---------------------------------------------------------------------------
# 接口请求
# ---------------------------------------------------------------------------
def _request(path, token, params=None):
    if not token:
        raise LiveDataError(
            "缺少 API token。请到 football-data.org 免费注册获取, "
            "并在界面填入或设置环境变量 FOOTBALL_DATA_TOKEN。")
    url = API_BASE + path
    if params:
        url += "?" + urlencode(params)
    req = Request(url, headers={"X-Auth-Token": token})
    try:
        resp = urlopen(req, timeout=25)
        raw = resp.read().decode("utf-8")
        return json.loads(raw)
    except HTTPError as e:
        if e.code == 403:
            raise LiveDataError(
                "接口返回 403: token 无效, 或你的套餐不包含该赛事 (世界杯)。")
        if e.code == 429:
            raise LiveDataError("接口返回 429: 请求过于频繁, 请稍后再试。")
        raise LiveDataError("接口返回 HTTP %s。" % e.code)
    except URLError as e:
        raise LiveDataError("网络连接失败: %s" % getattr(e, "reason", e))
    except Exception as e:
        raise LiveDataError("请求出错: %s" % e)


def team_name(team):
    """把 API 的球队对象转成中文队名 (无映射时退回英文简称)。"""
    if not team:
        return "待定"
    tla = team.get("tla")
    if tla and tla in TLA_TO_ZH:
        return TLA_TO_ZH[tla]
    return team.get("shortName") or team.get("name") or "待定"


def fetch_all_matches(token, competition=DEFAULT_COMPETITION):
    """拉取某赛事的全部比赛, 返回原始 match 列表。"""
    data = _request("/competitions/%s/matches" % competition, token)
    return data.get("matches", [])


def split_matches(matches):
    """把比赛拆成 (即将进行, 已结束) 两个列表 (已做队名映射与字段精简)。"""
    upcoming, finished = [], []
    for m in matches:
        home = team_name(m.get("homeTeam"))
        away = team_name(m.get("awayTeam"))
        status = m.get("status", "")
        stage = m.get("stage", "") or ""
        group = m.get("group") or ""
        date = (m.get("utcDate") or "")[:16].replace("T", " ")
        if status in ("SCHEDULED", "TIMED"):
            upcoming.append({"date": date, "home": home, "away": away,
                             "stage": stage, "group": group})
        elif status == "FINISHED":
            ft = (m.get("score") or {}).get("fullTime") or {}
            hg, ag = ft.get("home"), ft.get("away")
            if hg is not None and ag is not None:
                finished.append({"date": date, "home": home, "away": away,
                                 "home_goals": int(hg), "away_goals": int(ag),
                                 "stage": stage, "group": group})
    return upcoming, finished


def results_to_calibration_rows(finished, weight=1.5):
    """把已结束比赛转成 calibrate_ratings 需要的比分记录。"""
    return [(m["home"], m["away"], m["home_goals"], m["away_goals"], weight)
            for m in finished]


def rating_of(teams, name):
    """取球队评分, 未收录时返回默认值。"""
    return teams.get(name, DEFAULT_RATING)

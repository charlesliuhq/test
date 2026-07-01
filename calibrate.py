# -*- coding: utf-8 -*-
"""
命令行评分校准脚本
====================

用历史比分 CSV 对球队评分做 Elo 校准, 并写回 teams.json。

用法:
    python calibrate.py [历史比分.csv] [teams.json]

    - 第一个参数: 历史比分 CSV, 默认 historical_matches.csv
    - 第二个参数: 评分文件 (读入作为先验, 校准后写回), 默认 teams.json

CSV 需包含列: home, away, home_goals, away_goals  (可选 weight 列表示比赛权重)

注意: 仓库自带的 historical_matches.csv 仅为示例数据, 请替换为你自己的真实比分。
"""

import sys

from worldcup_predictor import (
    load_teams, save_teams, load_matches_csv, calibrate_ratings, DATA_FILE)


def main(argv):
    csv_path = argv[1] if len(argv) > 1 else "historical_matches.csv"
    teams_path = argv[2] if len(argv) > 2 else DATA_FILE

    teams = load_teams(teams_path)
    matches = load_matches_csv(csv_path)
    if not matches:
        print("未从 %s 读到有效比分记录。" % csv_path)
        return 1

    before = dict(teams)
    teams = calibrate_ratings(teams, matches)
    save_teams(teams, teams_path)

    print("已根据 %d 场比赛校准评分, 结果写入 %s\n" % (len(matches), teams_path))
    movers = []
    for name in teams:
        old = before.get(name)
        if old is not None:
            movers.append((name, old, teams[name], teams[name] - old))
        else:
            movers.append((name, None, teams[name], 0.0))
    movers.sort(key=lambda x: abs(x[3]), reverse=True)
    print("  %-8s %8s %8s %8s" % ("球队", "校准前", "校准后", "变化"))
    print("  " + "-" * 36)
    for name, old, new, delta in movers[:15]:
        old_s = "%.0f" % old if old is not None else "新增"
        print("  %-8s %8s %8.0f %+8.0f" % (name, old_s, new, delta))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

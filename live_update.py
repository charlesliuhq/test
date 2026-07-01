# -*- coding: utf-8 -*-
"""
命令行实时赛事工具 (football-data.org)
========================================

抓取真实赛程/赛果, 预测即将进行的比赛, 并用已结束比赛校准评分。

用法:
    python live_update.py [赛事代码] [teams.json]

    - 赛事代码: 默认 WC (2026 世界杯)
    - teams.json: 评分文件 (读入为先验, 校准后写回), 默认 teams.json

Token 来源: 环境变量 FOOTBALL_DATA_TOKEN, 或 config.json 里的 football_data_token。
    设置示例 (Windows):  set FOOTBALL_DATA_TOKEN=你的token
"""

import sys

import livedata
from worldcup_predictor import (
    load_teams, save_teams, predict_match, calibrate_ratings, DATA_FILE)


def main(argv):
    comp = argv[1] if len(argv) > 1 else livedata.DEFAULT_COMPETITION
    teams_path = argv[2] if len(argv) > 2 else DATA_FILE

    token = livedata.get_token()
    teams = load_teams(teams_path)

    try:
        matches = livedata.fetch_all_matches(token, comp)
    except livedata.LiveDataError as e:
        print("获取数据失败: %s" % e)
        return 1

    upcoming, finished = livedata.split_matches(matches)
    print("赛事 %s: 即将进行 %d 场, 已结束 %d 场\n"
          % (comp, len(upcoming), len(finished)))

    # 先用已结束比赛校准评分
    if finished:
        rows = livedata.results_to_calibration_rows(finished)
        teams = calibrate_ratings(teams, rows)
        save_teams(teams, teams_path)
        print("已用 %d 场赛果校准评分并写回 %s\n" % (len(finished), teams_path))

    # 预测即将进行的比赛
    if upcoming:
        print("即将进行的比赛预测:")
        print("-" * 60)
        for m in upcoming[:40]:
            ra = livedata.rating_of(teams, m["home"])
            rb = livedata.rating_of(teams, m["away"])
            res = predict_match(ra, rb)
            top = res["top_scores"][0]
            print("  %s  %s vs %s" % (m["date"], m["home"], m["away"]))
            print("      胜 %.0f%% / 平 %.0f%% / 负 %.0f%%   最可能 %d:%d"
                  % (res["win_a"] * 100, res["draw"] * 100,
                     res["win_b"] * 100, top[0], top[1]))
    else:
        print("暂无即将进行的比赛。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

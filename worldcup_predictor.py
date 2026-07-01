# -*- coding: utf-8 -*-
"""
世界杯比赛预测系统 (World Cup Match Predictor)
=================================================

特点:
    - 纯 Python 标准库实现, 无需安装任何第三方依赖
    - 使用 tkinter 图形界面, 可在 Windows 7 上运行
      (推荐 Python 3.6 ~ 3.8, 其中 3.8 是官方支持 Win7 的最后版本)
    - 预测模型: 球队实力评分 (类 Elo) + 泊松分布 (Poisson) 进球模型
    - 支持单场比赛预测、球队评分管理、整届赛事蒙特卡洛模拟

运行方式:
    双击运行, 或在命令行执行:  python worldcup_predictor.py

作者: Claude Code
"""

import csv
import json
import math
import os
import random
from itertools import combinations

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    HAS_TK = True
except Exception:  # pragma: no cover - 无图形环境时降级为命令行
    HAS_TK = False

try:
    import livedata  # 实时赛事数据 (football-data.org)
    HAS_LIVE = True
except Exception:  # 缺少 livedata.py 时不影响其余功能
    HAS_LIVE = False


# ---------------------------------------------------------------------------
# 数据: 默认球队评分 (数值越高实力越强, 参考 Elo/FIFA 排名, 可自行调整)
# ---------------------------------------------------------------------------
DEFAULT_TEAMS = {
    "阿根廷": 2100,
    "法国": 2080,
    "巴西": 2060,
    "英格兰": 2000,
    "西班牙": 1990,
    "葡萄牙": 1980,
    "荷兰": 1970,
    "比利时": 1950,
    "德国": 1945,
    "克罗地亚": 1920,
    "意大利": 1910,
    "乌拉圭": 1900,
    "摩洛哥": 1880,
    "哥伦比亚": 1870,
    "墨西哥": 1850,
    "美国": 1830,
    "瑞士": 1825,
    "塞内加尔": 1820,
    "丹麦": 1815,
    "日本": 1810,
    "韩国": 1790,
    "澳大利亚": 1770,
    "波兰": 1765,
    "厄瓜多尔": 1760,
    "沙特阿拉伯": 1700,
    "伊朗": 1720,
    "加纳": 1710,
    "喀麦隆": 1715,
    "加拿大": 1730,
    "卡塔尔": 1650,
    "突尼斯": 1705,
    "中国": 1580,
}

# 模型参数
BASE_GOALS = 2.6          # 一场比赛双方进球总数的经验期望
RATING_SCALE = 220.0      # 评分差换算成进球优势的比例尺 (越大差距影响越小)
MAX_GOALS = 8             # 泊松矩阵计算时单队最大进球数
DATA_FILE = "teams.json"  # 球队评分的默认存档文件名


# ---------------------------------------------------------------------------
# 核心预测模型
# ---------------------------------------------------------------------------
def poisson_pmf(k, lam):
    """泊松分布概率质量函数: P(X = k), 参数 lambda = lam。"""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def expected_goals(rating_a, rating_b):
    """
    根据两队评分计算各自的期望进球数 (lambda_a, lambda_b)。

    思路:
        - 评分差 -> 净胜球优势 (supremacy)
        - 在总进球期望 BASE_GOALS 的基础上按优势分配给两队
    """
    supremacy = (rating_a - rating_b) / RATING_SCALE
    lam_a = max(0.15, BASE_GOALS / 2.0 + supremacy / 2.0)
    lam_b = max(0.15, BASE_GOALS / 2.0 - supremacy / 2.0)
    return lam_a, lam_b


def score_matrix(rating_a, rating_b):
    """返回 (概率矩阵, lambda_a, lambda_b), 矩阵[i][j] = A 进 i 球且 B 进 j 球的概率。"""
    lam_a, lam_b = expected_goals(rating_a, rating_b)
    pa = [poisson_pmf(i, lam_a) for i in range(MAX_GOALS + 1)]
    pb = [poisson_pmf(j, lam_b) for j in range(MAX_GOALS + 1)]
    matrix = [[pa[i] * pb[j] for j in range(MAX_GOALS + 1)]
              for i in range(MAX_GOALS + 1)]
    return matrix, lam_a, lam_b


def predict_match(rating_a, rating_b):
    """
    预测单场比赛结果。

    返回字典:
        win_a / draw / win_b : A 胜 / 平局 / B 胜 的概率
        exp_a / exp_b        : 两队期望进球
        top_scores           : 最可能的若干比分 [(a, b, prob), ...]
    """
    matrix, lam_a, lam_b = score_matrix(rating_a, rating_b)
    win_a = draw = win_b = 0.0
    scores = []
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            p = matrix[i][j]
            scores.append((i, j, p))
            if i > j:
                win_a += p
            elif i == j:
                draw += p
            else:
                win_b += p
    scores.sort(key=lambda x: x[2], reverse=True)
    return {
        "win_a": win_a,
        "draw": draw,
        "win_b": win_b,
        "exp_a": lam_a,
        "exp_b": lam_b,
        "top_scores": scores[:5],
    }


def simulate_match(rating_a, rating_b, knockout=False):
    """
    随机模拟一场比赛, 返回 (goals_a, goals_b, winner)。
    winner 为 'A'/'B'/'draw'。若 knockout=True 则平局用点球随机决出胜者。
    """
    lam_a, lam_b = expected_goals(rating_a, rating_b)
    ga = _sample_poisson(lam_a)
    gb = _sample_poisson(lam_b)
    if ga > gb:
        winner = "A"
    elif ga < gb:
        winner = "B"
    else:
        winner = "draw"
    if knockout and winner == "draw":
        # 点球大战: 用评分给出的胜率随机决定
        pa = 0.5 + (rating_a - rating_b) / (RATING_SCALE * 20)
        pa = min(0.85, max(0.15, pa))
        winner = "A" if random.random() < pa else "B"
    return ga, gb, winner


def _sample_poisson(lam):
    """用 Knuth 算法从泊松分布采样一个整数。"""
    l = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= random.random()
        if p <= l:
            return k - 1


def simulate_tournament(teams, trials=2000):
    """
    对给定球队进行单败淘汰赛的蒙特卡洛模拟, 返回各队夺冠概率(0~1)。

    teams: dict {队名: 评分}。参赛队数会被裁剪到 2 的幂次 (取评分最高的若干队)。
    """
    names = sorted(teams, key=lambda n: teams[n], reverse=True)
    # 取最大的 2 的幂次支球队
    size = 1
    while size * 2 <= len(names):
        size *= 2
    bracket = names[:size]
    if size < 2:
        return {}

    wins = dict((n, 0) for n in bracket)
    for _ in range(trials):
        alive = list(bracket)
        random.shuffle(alive)
        while len(alive) > 1:
            nxt = []
            for k in range(0, len(alive), 2):
                a, b = alive[k], alive[k + 1]
                _, _, w = simulate_match(teams[a], teams[b], knockout=True)
                nxt.append(a if w == "A" else b)
            alive = nxt
        wins[alive[0]] += 1

    return dict((n, wins[n] / float(trials)) for n in bracket)


def _pick_group_config(n_teams):
    """根据可用球队数选择 (小组数, 每组队数)。返回 (0, 0) 表示球队不足。"""
    for n_groups in (8, 4, 2):
        if n_groups * 4 <= n_teams:
            return n_groups, 4
    return 0, 0


def simulate_full_tournament(teams, trials=1000):
    """
    完整世界杯赛制蒙特卡洛模拟: 小组循环赛 + 单败淘汰赛。

    流程:
        - 取评分最高的若干队, 随机分组 (8 组 x 4 队, 或按球队数自动缩减)
        - 小组赛单循环, 3/1/0 计分, 按 积分 -> 净胜球 -> 进球 排名, 每组前 2 出线
        - 出线队按标准交叉赛制进入淘汰赛 (组头 vs 另一组次名), 淘汰赛平局点球决胜
        - 统计每队 夺冠 / 进决赛 / 进四强 的概率

    返回: dict {队名: {"champion": p, "final": p, "semi": p}}
    """
    names = sorted(teams, key=lambda n: teams[n], reverse=True)
    n_groups, group_size = _pick_group_config(len(names))
    if n_groups == 0:
        return {}
    need = n_groups * group_size
    field = names[:need]

    stats = dict((n, {"champion": 0, "final": 0, "semi": 0}) for n in field)

    for _ in range(trials):
        order = list(field)
        random.shuffle(order)  # 随机抽签分组
        groups = [order[i * group_size:(i + 1) * group_size]
                  for i in range(n_groups)]

        winners, runners = [], []
        for g in groups:
            table = dict((t, [0, 0, 0]) for t in g)  # [积分, 净胜球, 进球]
            for a, b in combinations(g, 2):
                ga, gb, _ = simulate_match(teams[a], teams[b])
                table[a][1] += ga - gb
                table[b][1] += gb - ga
                table[a][2] += ga
                table[b][2] += gb
                if ga > gb:
                    table[a][0] += 3
                elif gb > ga:
                    table[b][0] += 3
                else:
                    table[a][0] += 1
                    table[b][0] += 1
            ranked = sorted(
                g,
                key=lambda t: (table[t][0], table[t][1], table[t][2],
                               random.random()),
                reverse=True)
            winners.append(ranked[0])
            runners.append(ranked[1])

        # 标准交叉赛制: 组头对阵相邻组的次名, 同组两队最早决赛才可能相遇
        alive = []
        for i in range(0, n_groups, 2):
            alive.append(winners[i])
            alive.append(runners[i + 1])
            alive.append(winners[i + 1])
            alive.append(runners[i])

        while len(alive) > 1:
            if len(alive) == 4:
                for t in alive:
                    stats[t]["semi"] += 1
            if len(alive) == 2:
                for t in alive:
                    stats[t]["final"] += 1
            nxt = []
            for k in range(0, len(alive), 2):
                a, b = alive[k], alive[k + 1]
                _, _, w = simulate_match(teams[a], teams[b], knockout=True)
                nxt.append(a if w == "A" else b)
            alive = nxt
        stats[alive[0]]["champion"] += 1

    return dict(
        (n, dict((k, v / float(trials)) for k, v in s.items()))
        for n, s in stats.items())


# ---------------------------------------------------------------------------
# 历史数据校准 (Elo)
# ---------------------------------------------------------------------------
def load_matches_csv(path):
    """
    读取历史比分 CSV, 需含列: home, away, home_goals, away_goals (可选 weight)。
    返回 [(home, away, home_goals, away_goals, weight), ...]
    """
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                home = r["home"].strip()
                away = r["away"].strip()
                hg = int(r["home_goals"])
                ag = int(r["away_goals"])
                weight = float(r.get("weight") or 1.0)
            except (KeyError, ValueError, AttributeError):
                continue
            if home and away:
                rows.append((home, away, hg, ag, weight))
    return rows


def calibrate_ratings(teams, matches, k=24.0, passes=1):
    """
    用历史比分对球队评分做 Elo 校准。

    以现有评分为先验, 逐场按实际结果与预期的偏差更新评分;
    进球差越大, 调整幅度越大 (对数缩放)。未收录的新球队以中位数评分加入。

    返回更新后的评分 dict (仅数值, 保留一位小数)。
    """
    ratings = dict(teams)
    if teams:
        vals = sorted(teams.values())
        default = vals[len(vals) // 2]
    else:
        default = 1700.0

    for _ in range(max(1, passes)):
        for home, away, hg, ag, weight in matches:
            ratings.setdefault(home, default)
            ratings.setdefault(away, default)
            ra, rb = ratings[home], ratings[away]
            exp_home = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))
            if hg > ag:
                actual = 1.0
            elif hg < ag:
                actual = 0.0
            else:
                actual = 0.5
            margin = abs(hg - ag)
            g = math.log(margin + 1.0) + 1.0  # 净胜球权重
            delta = k * weight * g * (actual - exp_home)
            ratings[home] = ra + delta
            ratings[away] = rb - delta

    return dict((n, round(r, 1)) for n, r in ratings.items())


# ---------------------------------------------------------------------------
# 数据存取
# ---------------------------------------------------------------------------
def load_teams(path=DATA_FILE):
    """从 JSON 文件读取球队评分; 文件不存在时返回默认数据的副本。"""
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return dict((str(k), float(v)) for k, v in data.items())
        except Exception:
            pass
    return dict(DEFAULT_TEAMS)


def save_teams(teams, path=DATA_FILE):
    """把球队评分写入 JSON 文件。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(teams, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 图形界面 (tkinter)
# ---------------------------------------------------------------------------
class PredictorApp(object):
    def __init__(self, root):
        self.root = root
        self.teams = load_teams()
        root.title("世界杯比赛预测系统")
        root.geometry("640x560")

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_match = ttk.Frame(notebook)
        self.tab_teams = ttk.Frame(notebook)
        self.tab_sim = ttk.Frame(notebook)
        notebook.add(self.tab_match, text="单场预测")
        notebook.add(self.tab_teams, text="球队评分")
        notebook.add(self.tab_sim, text="赛事模拟")

        self._build_match_tab()
        self._build_teams_tab()
        self._build_sim_tab()

        if HAS_LIVE:
            self.tab_live = ttk.Frame(notebook)
            notebook.add(self.tab_live, text="实时赛程")
            self._build_live_tab()

    # -- 单场预测 --------------------------------------------------------
    def _build_match_tab(self):
        frm = self.tab_match
        names = self._sorted_names()

        top = ttk.Frame(frm)
        top.pack(pady=12)
        ttk.Label(top, text="主队:").grid(row=0, column=0, padx=4)
        self.cb_a = ttk.Combobox(top, values=names, state="readonly", width=14)
        self.cb_a.grid(row=0, column=1, padx=4)
        self.cb_a.current(0)

        ttk.Label(top, text="VS").grid(row=0, column=2, padx=8)

        ttk.Label(top, text="客队:").grid(row=0, column=3, padx=4)
        self.cb_b = ttk.Combobox(top, values=names, state="readonly", width=14)
        self.cb_b.grid(row=0, column=4, padx=4)
        self.cb_b.current(1 if len(names) > 1 else 0)

        ttk.Button(frm, text="预测比赛", command=self.on_predict).pack(pady=6)

        self.txt_result = tk.Text(frm, height=18, width=70, state="disabled")
        self.txt_result.pack(padx=10, pady=8, fill="both", expand=True)

    def on_predict(self):
        a = self.cb_a.get()
        b = self.cb_b.get()
        if a == b:
            messagebox.showwarning("提示", "请选择两支不同的球队")
            return
        res = predict_match(self.teams[a], self.teams[b])
        lines = []
        lines.append("  %s (%d)   vs   %s (%d)" %
                     (a, int(self.teams[a]), b, int(self.teams[b])))
        lines.append("-" * 44)
        lines.append("  %s 获胜: %5.1f%%" % (a, res["win_a"] * 100))
        lines.append("  平    局: %5.1f%%" % (res["draw"] * 100))
        lines.append("  %s 获胜: %5.1f%%" % (b, res["win_b"] * 100))
        lines.append("")
        lines.append("  期望进球:  %s %.2f  -  %.2f %s" %
                     (a, res["exp_a"], res["exp_b"], b))
        lines.append("")
        lines.append("  最可能的比分:")
        for ga, gb, p in res["top_scores"]:
            lines.append("     %s %d : %d %s   (%.1f%%)" %
                         (a, ga, gb, b, p * 100))
        self._set_text(self.txt_result, "\n".join(lines))

    # -- 球队评分 --------------------------------------------------------
    def _build_teams_tab(self):
        frm = self.tab_teams
        self.tree = ttk.Treeview(frm, columns=("rating",), show="headings",
                                 height=14)
        self.tree.heading("rating", text="评分")
        self.tree.column("rating", width=100, anchor="center")
        # 第一列用 #0 显示队名
        self.tree.configure(show="tree headings")
        self.tree.heading("#0", text="球队")
        self.tree.column("#0", width=200)
        self.tree.pack(padx=10, pady=8, fill="both", expand=True)
        self._refresh_tree()

        edit = ttk.Frame(frm)
        edit.pack(pady=6)
        ttk.Label(edit, text="球队:").grid(row=0, column=0, padx=4)
        self.ent_name = ttk.Entry(edit, width=14)
        self.ent_name.grid(row=0, column=1, padx=4)
        ttk.Label(edit, text="评分:").grid(row=0, column=2, padx=4)
        self.ent_rating = ttk.Entry(edit, width=8)
        self.ent_rating.grid(row=0, column=3, padx=4)
        ttk.Button(edit, text="添加/更新", command=self.on_upsert_team).grid(
            row=0, column=4, padx=4)
        ttk.Button(edit, text="删除选中", command=self.on_delete_team).grid(
            row=0, column=5, padx=4)

        btns = ttk.Frame(frm)
        btns.pack(pady=4)
        ttk.Button(btns, text="保存到文件", command=self.on_save).grid(
            row=0, column=0, padx=4)
        ttk.Button(btns, text="从文件加载", command=self.on_load).grid(
            row=0, column=1, padx=4)
        ttk.Button(btns, text="恢复默认", command=self.on_reset).grid(
            row=0, column=2, padx=4)
        ttk.Button(btns, text="从历史数据校准", command=self.on_calibrate).grid(
            row=0, column=3, padx=4)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def _refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for name in self._sorted_names():
            self.tree.insert("", "end", text=name,
                             values=(int(self.teams[name]),))

    def _on_tree_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        name = self.tree.item(sel[0], "text")
        self.ent_name.delete(0, "end")
        self.ent_name.insert(0, name)
        self.ent_rating.delete(0, "end")
        self.ent_rating.insert(0, str(int(self.teams[name])))

    def on_upsert_team(self):
        name = self.ent_name.get().strip()
        if not name:
            messagebox.showwarning("提示", "请输入球队名称")
            return
        try:
            rating = float(self.ent_rating.get())
        except ValueError:
            messagebox.showwarning("提示", "评分必须是数字")
            return
        self.teams[name] = rating
        self._refresh_tree()
        self._refresh_comboboxes()

    def on_delete_team(self):
        sel = self.tree.selection()
        if not sel:
            return
        name = self.tree.item(sel[0], "text")
        if name in self.teams:
            del self.teams[name]
        self._refresh_tree()
        self._refresh_comboboxes()

    def on_save(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile=DATA_FILE,
            filetypes=[("JSON 文件", "*.json")])
        if not path:
            return
        try:
            save_teams(self.teams, path)
            messagebox.showinfo("成功", "已保存到:\n%s" % path)
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def on_load(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        self.teams = load_teams(path)
        self._refresh_tree()
        self._refresh_comboboxes()

    def on_reset(self):
        if messagebox.askyesno("确认", "确定要恢复默认球队评分吗?"):
            self.teams = dict(DEFAULT_TEAMS)
            self._refresh_tree()
            self._refresh_comboboxes()

    def on_calibrate(self):
        path = filedialog.askopenfilename(
            title="选择历史比分 CSV (列: home,away,home_goals,away_goals)",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            matches = load_matches_csv(path)
        except Exception as e:
            messagebox.showerror("错误", "读取失败: %s" % e)
            return
        if not matches:
            messagebox.showwarning("提示", "未读到有效比分记录。")
            return
        before = dict(self.teams)
        self.teams = calibrate_ratings(self.teams, matches)
        # 汇总变化最大的几支球队
        movers = []
        for name in self.teams:
            old = before.get(name)
            if old is not None:
                movers.append((name, self.teams[name] - old))
        movers.sort(key=lambda x: abs(x[1]), reverse=True)
        summary = "\n".join(
            "  %s: %+.0f" % (n, d) for n, d in movers[:8] if abs(d) >= 0.5)
        self._refresh_tree()
        self._refresh_comboboxes()
        messagebox.showinfo(
            "校准完成",
            "已根据 %d 场比赛校准评分。\n\n变化最大的球队:\n%s"
            % (len(matches), summary or "  (无明显变化)"))

    # -- 赛事模拟 --------------------------------------------------------
    def _build_sim_tab(self):
        frm = self.tab_sim
        top = ttk.Frame(frm)
        top.pack(pady=10)
        ttk.Label(top, text="赛制:").grid(row=0, column=0, padx=4)
        self.cb_mode = ttk.Combobox(
            top, state="readonly", width=22,
            values=["完整赛制 (小组赛+淘汰赛)", "单败淘汰赛"])
        self.cb_mode.current(0)
        self.cb_mode.grid(row=0, column=1, padx=4)
        ttk.Label(top, text="模拟次数:").grid(row=0, column=2, padx=4)
        self.ent_trials = ttk.Entry(top, width=8)
        self.ent_trials.insert(0, "2000")
        self.ent_trials.grid(row=0, column=3, padx=4)
        ttk.Button(top, text="开始模拟", command=self.on_simulate).grid(
            row=0, column=4, padx=8)

        ttk.Label(
            frm,
            text="(完整赛制取评分最高的 32/16/8 队分组; 单败淘汰取 2^n 队)").pack()

        self.txt_sim = tk.Text(frm, height=20, width=72, state="disabled")
        self.txt_sim.pack(padx=10, pady=8, fill="both", expand=True)

    def on_simulate(self):
        try:
            trials = int(self.ent_trials.get())
            trials = max(100, min(50000, trials))
        except ValueError:
            messagebox.showwarning("提示", "模拟次数必须是整数")
            return
        self._set_text(self.txt_sim, "模拟中, 请稍候...")
        self.root.update_idletasks()

        if self.cb_mode.current() == 0:
            self._run_full_sim(trials)
        else:
            self._run_knockout_sim(trials)

    def _run_knockout_sim(self, trials):
        probs = simulate_tournament(self.teams, trials=trials)
        if not probs:
            self._set_text(self.txt_sim, "球队数量不足, 至少需要 2 支球队。")
            return
        ranked = sorted(probs.items(), key=lambda x: x[1], reverse=True)
        lines = ["  夺冠概率预测 - 单败淘汰赛 (模拟 %d 次)" % trials, "-" * 44]
        for i, (name, p) in enumerate(ranked, 1):
            bar = "#" * int(round(p * 40))
            lines.append("  %2d. %-8s %5.1f%%  %s" % (i, name, p * 100, bar))
        self._set_text(self.txt_sim, "\n".join(lines))

    def _run_full_sim(self, trials):
        stats = simulate_full_tournament(self.teams, trials=trials)
        if not stats:
            self._set_text(self.txt_sim, "球队数量不足, 完整赛制至少需要 8 支球队。")
            return
        ranked = sorted(stats.items(),
                        key=lambda x: x[1]["champion"], reverse=True)
        lines = ["  完整赛制预测 (小组赛+淘汰赛, 模拟 %d 次)" % trials,
                 "  %-8s %8s %8s %8s" % ("球队", "夺冠", "进决赛", "进四强"),
                 "-" * 44]
        for name, s in ranked:
            lines.append("  %-8s %7.1f%% %7.1f%% %7.1f%%" % (
                name, s["champion"] * 100, s["final"] * 100, s["semi"] * 100))
        self._set_text(self.txt_sim, "\n".join(lines))

    # -- 实时赛程 --------------------------------------------------------
    def _build_live_tab(self):
        frm = self.tab_live
        cfg = livedata.load_config()

        row = ttk.Frame(frm)
        row.pack(pady=8, fill="x", padx=10)
        ttk.Label(row, text="API Token:").grid(row=0, column=0, padx=4)
        self.ent_token = ttk.Entry(row, width=34, show="*")
        self.ent_token.grid(row=0, column=1, padx=4)
        self.ent_token.insert(0, str(cfg.get("football_data_token", "")))
        ttk.Button(row, text="保存 Token", command=self.on_save_token).grid(
            row=0, column=2, padx=4)
        ttk.Label(row, text="(football-data.org 免费注册获取)").grid(
            row=1, column=1, sticky="w", padx=4)

        row2 = ttk.Frame(frm)
        row2.pack(pady=4)
        ttk.Label(row2, text="赛事代码:").grid(row=0, column=0, padx=4)
        self.ent_comp = ttk.Entry(row2, width=8)
        self.ent_comp.insert(0, livedata.DEFAULT_COMPETITION)  # WC = 世界杯
        self.ent_comp.grid(row=0, column=1, padx=4)
        ttk.Button(row2, text="获取赛程并预测",
                   command=self.on_fetch_fixtures).grid(row=0, column=2, padx=6)
        ttk.Button(row2, text="更新赛果并校准评分",
                   command=self.on_update_results).grid(row=0, column=3, padx=6)

        self.txt_live = tk.Text(frm, height=18, width=74, state="disabled")
        self.txt_live.pack(padx=10, pady=8, fill="both", expand=True)
        self._set_text(
            self.txt_live,
            "  使用说明:\n"
            "  1. 填入 football-data.org 的免费 API Token 并保存\n"
            "  2. 赛事代码默认 WC (2026 世界杯), 点『获取赛程并预测』\n"
            "  3. 点『更新赛果并校准评分』可用已结束比赛自动校准球队评分\n"
            "  (需要联网; 世界杯数据是否可用取决于你的 football-data 套餐)")

    def on_save_token(self):
        cfg = livedata.load_config()
        cfg["football_data_token"] = self.ent_token.get().strip()
        try:
            livedata.save_config(cfg)
            messagebox.showinfo("成功", "Token 已保存到 config.json")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _current_token(self):
        return livedata.get_token(self.ent_token.get().strip())

    def _fetch_split(self):
        """拉取并拆分比赛, 返回 (upcoming, finished) 或抛出 LiveDataError。"""
        token = self._current_token()
        comp = self.ent_comp.get().strip() or livedata.DEFAULT_COMPETITION
        matches = livedata.fetch_all_matches(token, comp)
        return livedata.split_matches(matches)

    def on_fetch_fixtures(self):
        self._set_text(self.txt_live, "正在获取赛程, 请稍候...")
        self.root.update_idletasks()
        try:
            upcoming, finished = self._fetch_split()
        except livedata.LiveDataError as e:
            self._set_text(self.txt_live, "获取失败:\n  %s" % e)
            return
        if not upcoming:
            self._set_text(
                self.txt_live,
                "没有『即将进行』的比赛。\n"
                "(已结束比赛 %d 场, 可点『更新赛果并校准评分』)" % len(finished))
            return
        lines = ["  即将进行的比赛预测 (共 %d 场)" % len(upcoming), "-" * 60]
        for m in upcoming[:40]:
            ra = livedata.rating_of(self.teams, m["home"])
            rb = livedata.rating_of(self.teams, m["away"])
            res = predict_match(ra, rb)
            top = res["top_scores"][0]
            lines.append("  %s  %s vs %s" % (m["date"], m["home"], m["away"]))
            lines.append("      胜 %.0f%% / 平 %.0f%% / 负 %.0f%%   最可能 %d:%d" % (
                res["win_a"] * 100, res["draw"] * 100, res["win_b"] * 100,
                top[0], top[1]))
        self._set_text(self.txt_live, "\n".join(lines))

    def on_update_results(self):
        self._set_text(self.txt_live, "正在获取赛果并校准, 请稍候...")
        self.root.update_idletasks()
        try:
            upcoming, finished = self._fetch_split()
        except livedata.LiveDataError as e:
            self._set_text(self.txt_live, "获取失败:\n  %s" % e)
            return
        if not finished:
            self._set_text(self.txt_live, "暂无已结束的比赛可用于校准。")
            return
        rows = livedata.results_to_calibration_rows(finished)
        before = dict(self.teams)
        self.teams = calibrate_ratings(self.teams, rows)
        self._refresh_tree()
        self._refresh_comboboxes()
        movers = []
        for name in self.teams:
            old = before.get(name)
            if old is not None:
                movers.append((name, self.teams[name] - old))
        movers.sort(key=lambda x: abs(x[1]), reverse=True)
        lines = ["  已用 %d 场赛果校准评分。" % len(finished), "-" * 40,
                 "  变化最大的球队:"]
        for n, d in movers[:10]:
            if abs(d) >= 0.5:
                lines.append("     %s: %+.0f" % (n, d))
        lines.append("")
        lines.append("  最近赛果:")
        for m in finished[-8:]:
            lines.append("     %s  %s %d:%d %s" % (
                m["date"], m["home"], m["home_goals"],
                m["away_goals"], m["away"]))
        self._set_text(self.txt_live, "\n".join(lines))

    # -- 辅助 ------------------------------------------------------------
    def _sorted_names(self):
        return sorted(self.teams, key=lambda n: self.teams[n], reverse=True)

    def _refresh_comboboxes(self):
        names = self._sorted_names()
        cur_a = self.cb_a.get()
        cur_b = self.cb_b.get()
        self.cb_a["values"] = names
        self.cb_b["values"] = names
        if cur_a in names:
            self.cb_a.set(cur_a)
        elif names:
            self.cb_a.current(0)
        if cur_b in names:
            self.cb_b.set(cur_b)
        elif names:
            self.cb_b.current(0)

    @staticmethod
    def _set_text(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")


# ---------------------------------------------------------------------------
# 命令行降级模式 (无图形环境时)
# ---------------------------------------------------------------------------
def run_cli():
    teams = load_teams()
    print("=" * 50)
    print(" 世界杯比赛预测系统 (命令行模式)")
    print("=" * 50)
    names = sorted(teams, key=lambda n: teams[n], reverse=True)
    for i, n in enumerate(names, 1):
        print("  %2d. %-8s %d" % (i, n, int(teams[n])))
    print("-" * 50)
    try:
        a = input("请输入主队名称: ").strip()
        b = input("请输入客队名称: ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if a not in teams or b not in teams:
        print("球队名称不存在。")
        return
    res = predict_match(teams[a], teams[b])
    print("\n  %s 胜: %.1f%%   平: %.1f%%   %s 胜: %.1f%%" %
          (a, res["win_a"] * 100, res["draw"] * 100, b, res["win_b"] * 100))
    print("  期望进球: %s %.2f - %.2f %s" % (a, res["exp_a"], res["exp_b"], b))
    print("  最可能比分:")
    for ga, gb, p in res["top_scores"]:
        print("     %s %d:%d %s  (%.1f%%)" % (a, ga, gb, b, p * 100))


def main():
    if HAS_TK:
        try:
            root = tk.Tk()
            PredictorApp(root)
            root.mainloop()
            return
        except tk.TclError:
            pass  # 无显示环境, 降级到命令行
    run_cli()


if __name__ == "__main__":
    main()

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

import json
import math
import os
import random

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    HAS_TK = True
except Exception:  # pragma: no cover - 无图形环境时降级为命令行
    HAS_TK = False


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

    # -- 赛事模拟 --------------------------------------------------------
    def _build_sim_tab(self):
        frm = self.tab_sim
        top = ttk.Frame(frm)
        top.pack(pady=10)
        ttk.Label(top, text="模拟次数:").grid(row=0, column=0, padx=4)
        self.ent_trials = ttk.Entry(top, width=10)
        self.ent_trials.insert(0, "2000")
        self.ent_trials.grid(row=0, column=1, padx=4)
        ttk.Button(top, text="开始模拟", command=self.on_simulate).grid(
            row=0, column=2, padx=8)

        ttk.Label(frm, text="(取评分最高的 2^n 支球队进行单败淘汰赛模拟)").pack()

        self.txt_sim = tk.Text(frm, height=20, width=70, state="disabled")
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

        probs = simulate_tournament(self.teams, trials=trials)
        if not probs:
            self._set_text(self.txt_sim, "球队数量不足, 至少需要 2 支球队。")
            return
        ranked = sorted(probs.items(), key=lambda x: x[1], reverse=True)
        lines = ["  夺冠概率预测 (模拟 %d 次)" % trials, "-" * 40]
        for i, (name, p) in enumerate(ranked, 1):
            bar = "#" * int(round(p * 40))
            lines.append("  %2d. %-8s %5.1f%%  %s" % (i, name, p * 100, bar))
        self._set_text(self.txt_sim, "\n".join(lines))

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

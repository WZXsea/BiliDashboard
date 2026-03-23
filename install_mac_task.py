#!/usr/bin/env python3
import os
import platform
import subprocess
import sys
import datetime
import plistlib
import glob
import re

# ============ 1. 全局配置与基础路径 ============
PROJECT_BASE_LABEL = "com.bilibili.dailyreport"
PLIST_DIR = os.path.expanduser("~/Library/LaunchAgents")
WORKING_DIR = os.path.dirname(os.path.abspath(__file__))

def print_header():
    print("\n" + "="*50)
    print("📺 Bilibili Daily Dashboard | 交互控台 v0.2.0")
    print("👨‍💻 Author: weizixun | Enhanced Interactive Edition")
    print("="*50)

# ============ 2. 深度巡检模块 ============

def parse_pmset_time(raw_out):
    """提取硬件重复唤醒时间"""
    match = re.search(r"wakepoweron at (\d+:\d+(?::\d+)?(?:AM|PM)?)", raw_out)
    if not match: return None
    ts = match.group(1)
    try:
        t_obj = datetime.datetime.strptime(ts, "%I:%M%p" if "AM" in ts or "PM" in ts else "%H:%M")
        return t_obj.strftime("%H:%M")
    except: return ts

def run_global_audit():
    """扫描系统排盘，支持多维度展示"""
    print("\n[📊 实时全域任务仪表盘]")
    discovered = []
    potential_files = set(glob.glob(os.path.join(PLIST_DIR, "*bilibili*.plist")) + 
                          glob.glob(os.path.join(PLIST_DIR, "*dailyreport*.plist")))
    
    for p_path in potential_files:
        try:
            with open(p_path, 'rb') as f:
                pl = plistlib.load(f)
                intervals = pl.get('StartCalendarInterval', [])
                if isinstance(intervals, dict): intervals = [intervals]
                times = [f"{i.get('Hour', 0):02d}:{i.get('Minute', 0):02d}" for i in intervals]
                label = pl.get('Label', os.path.basename(p_path))
                discovered.append({"label": label, "times": times, "path": p_path})
        except: continue

    if discovered:
        discovered.sort(key=lambda x: x['times'][0] if x['times'] else "99:99")
        for i, t in enumerate(discovered, 1):
            print(f"  🔹 [任务 {i}]: {t['label']} ➔ 定时: {t['times']}")
    else:
        print("  💡 (当前系统无活跃的后台任务)")

    try:
        sched_out = subprocess.check_output(["pmset", "-g", "sched"]).decode()
        wt = parse_pmset_time(sched_out)
        if wt: print(f"  📅 [硬件排班]: 每日 {wt} (唤醒主板)")
        else: print("  ❌ [硬件状态]: 未检测到强制唤醒设置")
    except: pass
    
    print("-" * 50)
    return discovered

# ============ 3. 原子化部署逻辑 ============

def deploy_atomic_times(time_list):
    python_bin = subprocess.check_output(["which", "python3"]).strip().decode()
    script_file = os.path.join(WORKING_DIR, "bili_daily_report.py")
    
    count = 0
    for h, m in time_list:
        tag = f"{h:02d}{m:02d}"
        label = f"{PROJECT_BASE_LABEL}_{tag}"
        target = os.path.join(PLIST_DIR, f"{label}.plist")
        
        plist_data = {
            'Label': label, 'ProgramArguments': [python_bin, script_file],
            'WorkingDirectory': WORKING_DIR, 'StartCalendarInterval': {'Hour': h, 'Minute': m},
            'StandardOutPath': os.path.join(WORKING_DIR, f"daily_cron_{tag}.log"),
            'StandardErrorPath': os.path.join(WORKING_DIR, f"daily_cron_{tag}.err")
        }
        
        try:
            subprocess.run(["launchctl", "unload", target], capture_output=True)
            with open(target, "wb") as f: plistlib.dump(plist_data, f)
            subprocess.run(["launchctl", "load", "-w", target], check=True)
            count += 1
        except: continue
    return count

def delete_interactive(tasks):
    """精细删除逻辑：先复显列表，再执行删除"""
    print("\n🗑  [删除确认] 请选择要注销的任务编号：")
    for i, t in enumerate(tasks, 1):
        print(f"   [{i}] {t['label']} ➔ {t['times']}")
    
    idx_in = input("\n👉 编号 (例 1 或 1,2)，按回车返回: ").strip()
    if not idx_in: return
    try:
        targets = [int(x.strip()) for x in idx_in.split(",") if x.strip().isdigit()]
        for idx in targets:
            if 1 <= idx <= len(tasks):
                t = tasks[idx-1]
                subprocess.run(["launchctl", "unload", t['path']], capture_output=True)
                if os.path.exists(t['path']): os.remove(t['path'])
                print(f"  ✅ 精准移除: {t['label']}")
        
        if input("\n⏰ 是否同步清理硬件唤醒记录？ (y/n): ").lower() == 'y':
            subprocess.run(["sudo", "pmset", "repeat", "cancel"], check=True)
            print("✅ 硬件计划已注销。")
    except: print("⚠️ 删除受阻。")

# ============ 4. 主控循环逻辑 ============

def main():
    print_header()
    if platform.system() != "Darwin": print("❌ 仅支持 macOS。"); exit(1)

    while True:
        tasks = run_global_audit()
        print("👉 请选择您的行动项：")
        print("  [Y] 批量设置/更新任务时刻 (原子化)")
        print("  [D] 定点删除后台任务 (Selective Remove)")
        print("  [X] 一键注销全域相关任务 (Uninstall All)")
        print("  [E] 退出助手 (Exit)")
        
        choice = input("\n👉 指令: ").strip().upper()
        if choice == 'E': break
        elif choice == 'X' and tasks:
            for t in tasks:
                subprocess.run(["launchctl", "unload", t['path']], capture_output=True)
                if os.path.exists(t['path']): os.remove(t['path'])
            subprocess.run(["sudo", "pmset", "repeat", "cancel"], check=True)
            print("✅ 全域设置已重置。")
        elif choice == 'D' and tasks:
            delete_interactive(tasks)
        elif choice == 'Y':
            print("\n⏰ 请输入时间点，用逗号隔开,支持多个时间设定 (如 08:30, 20:00)")
            raw_t = input("👉 设置时间序列: ").strip()
            if not raw_t: raw_t = "08:30"
            try:
                parsed = []
                for pt in raw_t.replace("，", ",").split(","):
                    h, m = map(int, pt.strip().split(":"))
                    if 0 <= h < 24 and 0 <= m < 60: parsed.append((h, m))
                if parsed:
                    count = deploy_atomic_times(parsed)
                    print(f"✅ 成功部署 {count} 个独立守护进程。")
                    earliest = min(parsed, key=lambda x: x[0]*60 + x[1])
                    ed = datetime.datetime.strptime(f"{earliest[0]}:{earliest[1]}", "%H:%M") - datetime.timedelta(minutes=2)
                    wh, wm = ed.hour, ed.minute
                    if input(f"🍎 是否同步注入 {wh:02d}:{wm:02d} 硬件唤醒？ (y/n): ").lower() == 'y':
                        print("🔑 正在请求授权...")
                        subprocess.run(["sudo", "pmset", "repeat", "wakeorpoweron", "MTWRFSU", f"{wh:02d}:{wm:02d}:00"], check=True)
                        print(f"✅ 硬件闹钟锁定：每日 {wh:02d}:{wm:02d}。")
            except: print("⚠️ 操作意外终止。")
        else: print("\n⚠️ 无效指令或暂无任务可操作。")
        
        print("\n" + "."*20 + " [仪表盘已即时刷新] " + "."*20)

if __name__ == "__main__":
    main()

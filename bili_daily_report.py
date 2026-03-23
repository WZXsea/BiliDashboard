#!/usr/bin/env python3
import httpx
import json
import time
import datetime
import os
import sys
import asyncio
import urllib3
import shutil
import subprocess
import platform

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============ 1. 基础常量与环境声明 ============
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = SCRIPT_DIR
DATA_DIR = os.path.join(WORK_DIR, "data")
CONFIG_FILE = os.path.join(WORK_DIR, "config.yaml")
CRED_DIR = os.path.join(DATA_DIR, "credentials")
CRED_FILE = os.path.join(DATA_DIR, "bili_credential.json")

# ============ 2. 工具函数 ============
def send_notification(title, message, sound="Glass"):
    """发送 macOS 原生通知"""
    if platform.system() == "Darwin":
        try:
            script = f'display notification "{message}" with title "{title}" sound name "{sound}"'
            subprocess.run(["osascript", "-e", script], capture_output=True)
        except: pass
    else:
        print(f"[Notice] {title}: {message}")

def load_config():
    """加载配置，不存在则引导创建"""
    import yaml
    if not os.path.exists(CONFIG_FILE):
        create_config_interactive(yaml)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def create_config_interactive(yaml):
    print("\n" + "="*50 + "\n⚙️ 首次运行：快速初始化配置\n" + "="*50)
    kimi_key = input("🔑 请输入您的 Kimi AI API Key: ").strip()
    tracked = {"原神": 401742377, "明日方舟": 161775300}
    config = {"kimi_api_key": kimi_key, "tracked_uids": tracked}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    print(f"✅ 配置已生成！")

# ============ 3. 账号管理 (多账号控制中心) ============
async def ensure_credential():
    from bilibili_api import Credential
    os.makedirs(CRED_DIR, exist_ok=True)
    
    accounts = []
    if os.path.exists(CRED_DIR):
        for f in [x for x in os.listdir(CRED_DIR) if x.endswith(".json")]:
            fpath = os.path.join(CRED_DIR, f)
            try:
                with open(fpath, "r") as jf:
                    data = json.load(jf)
                    accounts.append({
                        "name": data.get("uname", "未知"),
                        "uid": data.get("dedeuserid"),
                        "path": fpath,
                        "mtime": os.path.getmtime(fpath)
                    })
            except: continue

    accounts.sort(key=lambda x: x['mtime'], reverse=True)
    
    # 引导扫码流程
    if not accounts: return await qrcode_login()

    print("\n" + "-"*50 + "\n👤 请选择登录账号 (10秒超时将使用默认上次账号)\n" + "-"*50)
    for i, acc in enumerate(accounts, 1):
        print(f"  [{i}] {acc['name']} (UID: {acc['uid']})")
    print("\n  [N] 扫码添加新账号\n  [D] 进入删除菜单\n  [Q] 退出程序")

    choice = '1'
    if sys.stdin.isatty():
        import select
        r, _, _ = select.select([sys.stdin], [], [], 10)
        if r: choice = sys.stdin.readline().strip().upper()
    
    if choice == 'Q': sys.exit(0)
    if choice == 'D': await delete_account_menu(accounts); return await ensure_credential()
    if choice == 'N': return await qrcode_login()
    
    idx = int(choice)-1 if choice.isdigit() and 0 < int(choice) <= len(accounts) else 0
    target_path = accounts[idx]['path']
    os.utime(target_path, None) # 标记为最近活跃
    return get_cred_from_file(target_path)

async def delete_account_menu(accounts):
    print("\n🗑  删除管理：请输入对应编号删除，按 B 返回。")
    c = input("👉 ").strip().upper()
    if c.isdigit() and 0 < int(c) <= len(accounts):
        os.remove(accounts[int(c)-1]['path'])
        print("✅ 已移除该账号凭据。")

def get_cred_from_file(path):
    from bilibili_api import Credential
    with open(path, "r") as f:
        c = json.load(f)
        return Credential(
            sessdata=c.get('sessdata',''),
            bili_jct=c.get('bili_jct',''),
            buvid3=c.get('buvid3',''),
            dedeuserid=c.get('dedeuserid','')
        )

async def qrcode_login():
    print("\n" + "="*50 + "\n📱 开启新账号扫码登录\n" + "="*50)
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    async with httpx.AsyncClient(verify=False, headers=headers) as client:
        r_json = (await client.get("https://passport.bilibili.com/x/passport-login/web/qrcode/generate")).json()
        r = r_json.get("data", {})
        qr_url, qr_key = r.get("url"), r.get("qrcode_key")
    
    import qrcode
    qr = qrcode.QRCode(box_size=1, border=1)
    qr.add_data(qr_url)
    qr.print_ascii(invert=True)
    
    print("⏳ 请使用 B 站手机 App 扫码...")
    for _ in range(90):
        await asyncio.sleep(2)
        async with httpx.AsyncClient(verify=False, headers=headers) as client:
            poll_res = await client.get("https://passport.bilibili.com/x/passport-login/web/qrcode/poll", params={"qrcode_key": qr_key})
            p = poll_res.json().get("data", {})
            if p.get("code") == 0:
                # 扫码成功，获取详情
                async with httpx.AsyncClient(cookies=poll_res.cookies, verify=False, headers=headers) as c2:
                    nav = (await c2.get("https://api.bilibili.com/x/web-interface/nav")).json().get("data", {})
                    uname, uid = nav.get("uname", "新用户"), nav.get("mid", "unknown")
                
                c_data = {
                    "sessdata": poll_res.cookies.get("SESSDATA"),
                    "bili_jct": poll_res.cookies.get("bili_jct"),
                    "buvid3": poll_res.cookies.get("buvid3"),
                    "dedeuserid": str(uid),
                    "uname": uname
                }
                save_path = os.path.join(CRED_DIR, f"{uid}_{uname}.json")
                with open(save_path, "w", encoding="utf-8") as f: json.dump(c_data, f, indent=2, ensure_ascii=False)
                print(f"🎉 登录成功，欢迎: {uname}")
                return get_cred_from_file(save_path)
    print("❌ 扫码超时，请重试。")
    sys.exit(1)

# ============ 4. 数据抓取逻辑 ============
def format_number(num): return f"{num/10000:.1f}万" if num >= 10000 else str(num)

async def fetch_data(cred):
    cookies = {"SESSDATA": cred.sessdata, "bili_jct": cred.bili_jct}
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    struct_data = {"user_name": "同学", "history": [], "hot": [], "tech": [], "games": []}
    raw_texts = []
    
    # 用于记录需要修正的名字
    updated_uids = {}
    config_changed = False

    async with httpx.AsyncClient(cookies=cookies, headers=headers, verify=False, timeout=30.0) as client:
        # 0. 用户名
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 正在连线 B站 获取账号详情...")
        nav_req = await client.get("https://api.bilibili.com/x/web-interface/nav")
        nav = nav_req.json().get("data", {})
        struct_data["user_name"] = nav.get("uname", "同学")
        print(f"✅ 身份识别：{struct_data['user_name']}")

        # 1. 历史记录 (昨日观看时长)
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 正在检索您的历史足迹...")
        hist_req = await client.get("https://api.bilibili.com/x/web-interface/history/cursor")
        hist = hist_req.json().get("data", {}).get("list", [])
        total_sec = 0
        for item in hist:
            prog, dur = item.get("progress", 0), item.get("duration", 0)
            total_sec += dur if prog == -1 else (prog if prog > 0 else 0)
        
        minutes_watched = total_sec // 60
        watch_time_str = f"{minutes_watched // 60}小时 {minutes_watched % 60}分钟" if minutes_watched >= 60 else f"{minutes_watched}分钟"
        
        for i in hist[:8]:
            duration_sec = i.get('duration', 0)
            dur_str = f"{duration_sec // 60:02d}:{duration_sec % 60:02d}"
            struct_data["history"].append({
                "title": i.get('title', '无标题'), 
                "author": i.get('author_name', '未知'),
                "cover": i.get('cover', '').replace('http:', 'https:'),
                "url": f"https://www.bilibili.com/video/{i.get('history', {}).get('bvid', '')}",
                "duration": dur_str,
                "play_count": "", # 历史记录通常不带播放量
                "danmaku": "",
                "pub_date": datetime.datetime.fromtimestamp(i.get('view_at', 0)).strftime('%m-%d')
            })
        print(f"📊 昨日活跃：{watch_time_str} | 已记录 {len(struct_data['history'])} 条精选记录")
        raw_texts.append(f"昨日观看时长：{watch_time_str}\n历史简报: " + ", ".join([h['title'] for h in struct_data["history"][:5]]))

        # 2. 全站热门与科技
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 正在同步全站热榜与科技区看板...")
        for key, url, label in [("hot", "https://api.bilibili.com/x/web-interface/popular?ps=10", "全站热门"), ("tech", "https://api.bilibili.com/x/web-interface/ranking/v2?rid=188", "科技巅峰")]:
            res = (await client.get(url)).json().get("data", {}).get("list", [])
            for i in res[:8]:
                stat = i.get('stat', {})
                # 时长格式化
                duration_sec = i.get('duration', 0)
                dur_str = f"{duration_sec // 60:02d}:{duration_sec % 60:02d}"
                
                struct_data[key].append({
                    "title": i.get('title', ''), 
                    "author": i.get('owner', {}).get('name', ''),
                    "cover": i.get('pic', '').replace('http:', 'https:'),
                    "url": f"https://www.bilibili.com/video/{i.get('bvid', '')}",
                    "play_count": format_number(stat.get('view', 0)),
                    "danmaku": format_number(stat.get('danmaku', 0)),
                    "duration": dur_str,
                    "pub_date": datetime.datetime.fromtimestamp(i.get('pubdate', 0)).strftime('%m-%d')
                })
            print(f"🔥 {label}：已锁定前 {len(struct_data[key])} 名")

        # 3. 关注 UP 主动态 (采用稳定版解析逻辑)
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 正在巡航关注列表动态...")
        from bilibili_api import user
        now_ts = int(time.time())
        for name, uid in TRACKED_UIDS.items():
            print(f" 🛰  正在侦察: {name}...", end="", flush=True)
            record = {"name": name, "uid": uid, "posts": [], "videos": [], "avatar": "", "header": ""}
            try:
                u = user.User(uid, credential=cred)
                uinfo = await u.get_user_info()
                
                # 名号校验逻辑
                real_name = uinfo.get("name")
                if real_name and real_name != name:
                    print(f" | 📝 更正: {name} -> {real_name}", end="", flush=True)
                    record["name"] = real_name
                    config_changed = True
                    updated_uids[real_name] = uid
                else:
                    updated_uids[name] = uid

                record["avatar"] = (uinfo.get("face") or "").replace('http:', 'https:')
                header = uinfo.get("top_photo") or ""
                if header and not header.startswith("http"): header = "https://i0.hdslb.com/" + header
                record["header"] = header.replace('http:', 'https:')

                # A. 抓取动态 (最近 24 小时)
                dyn_res = await u.get_dynamics_new()
                items = dyn_res.get("items", [])
                
                for item in items:
                    auth = item.get("modules", {}).get("module_author") or {}
                    pub_ts = int(auth.get("pub_ts", 0))
                    if now_ts - pub_ts > 86400: continue
                    
                    mod_dyn = item.get("modules", {}).get("module_dynamic") or {}
                    desc = (mod_dyn.get("desc") or {}).get("text", "")
                    pics = []
                    major = mod_dyn.get("major") or {}
                    
                    if 'opus' in major:
                        opus = major.get('opus') or {}
                        if not desc: desc = (opus.get('summary') or {}).get('text', '') or opus.get('title', '')
                        if opus.get('pics'): 
                            pics = [p.get('url', '').replace('http:', 'https:') for p in opus['pics'][:9]]
                    elif 'archive' in major:
                        archive = major.get('archive') or {}
                        if not desc: desc = archive.get('title', '')
                        pics = [archive.get('cover', '').replace('http:', 'https:')]
                    
                    if not desc: desc = "分享了新内容"
                    
                    # 🚀 中奖过滤逻辑 (过滤“恭喜@xxx中奖”类干扰信息)
                    # 规则：如果包含“恭喜”、“中奖”、“已私信”、“详情请点击抽奖”等关键词，且名字不含本用户，则剔除
                    is_lottery = any(k in desc for k in ["中奖", "已私信通知", "详情请点击抽奖"])
                    if "恭喜" in desc and is_lottery:
                        my_name = struct_data.get("user_name", "同学")
                        if my_name != "同学" and my_name not in desc:
                            continue # 别人的中奖动态，跳过

                    record["posts"].append({
                        "text": desc[:2000], 
                        "pics": pics,
                        "cover": pics[0] if pics else "",
                        "url": f"https://t.bilibili.com/{item.get('id_str', '')}",
                        "time": datetime.datetime.fromtimestamp(pub_ts).strftime("%m-%d %H:%M")
                    })

                # B. 抓取最近视频 (前 3 条)
                v_res = await u.get_videos(ps=3)
                v_list = v_res.get("list", {}).get("vlist", [])
                for v in v_list:
                    record["videos"].append({
                        "title": v.get("title", ""),
                        "cover": v.get("pic", "").replace('http:', 'https:'),
                        "bvid": v.get("bvid", ""),
                        "play": format_number(v.get("play", 0)),
                        "time": datetime.datetime.fromtimestamp(v.get("created", 0)).strftime("%m-%d")
                    })
                
                struct_data["games"].append(record)
                display_name = record["name"]
                print(f" | 📡 捕获到 {len(record['posts'])} 条动态")
                raw_texts.append(f"UP主 {display_name} 有 {len(record['posts'])} 条新动态。")
            except Exception as e: 
                updated_uids[name] = uid
                print(f" | ⚠️ 抓取跳过: {e}")

    return struct_data, watch_time_str, minutes_watched, "\n".join(raw_texts), updated_uids, config_changed

# ============ 5. AI 与 展示 ============
AI_PRESETS = {
    "kimi": {"base_url": "https://api.moonshot.cn/v1", "model": "kimi-k2.5"},
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"}
}

async def generate_summary(config, text):
    try:
        # 获取 AI 配置，优先使用 ai_config，支持 provider 预设
        ai_config = config.get("ai_config", {})
        provider = ai_config.get("provider", "").lower()
        preset = AI_PRESETS.get(provider, {})

        api_key = ai_config.get("api_key") or config.get("kimi_api_key")
        base_url = ai_config.get("base_url") or preset.get("base_url") or "https://api.moonshot.cn/v1"
        model = ai_config.get("model") or preset.get("model") or "kimi-k2.5"
        
        if not api_key: return "未配置 AI API Key。"

        # 动态构造 OpenAI 兼容接口地址
        api_url = f"{base_url.rstrip('/')}/chat/completions"
        
        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "你是一个幽默的B站早报撰写专家"},
                    {"role": "user", "content": f"请基于以下数据写一段300字内总结: {text}"}
                ]
            }
            r = await client.post(api_url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"], model
    except Exception as e:
        print(f"❌ AI 总结生成失败: {e}")
        return "AI总结由于网络波动或配置错误未生成。", "Unknown"

async def main():
    print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] >>> B站早报脚本启动中...")
    config = load_config()
    global TRACKED_UIDS; TRACKED_UIDS = config.get("tracked_uids", {})
    cred = await ensure_credential()
    
    print("🚀 正在为您拼命抓取数据...")
    struct_data, watch_time, min_watched, raw_txt, updated_tracked, changed = await fetch_data(cred)
    
    # 自动同步配置
    if changed:
        config["tracked_uids"] = updated_tracked
        import yaml
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        print(f"♻️ 配置已自动同步：UP主名号已更正")

    ai_sum, used_model = await generate_summary(config, raw_txt)
    
    # ✍️ 导出隔离备份
    now = datetime.datetime.now()
    date_str, time_str = now.strftime("%Y-%m-%d"), now.strftime("%H%M")
    daily_snapshot_dir = os.path.join(WORK_DIR, "daily_notes", date_str)
    os.makedirs(daily_snapshot_dir, exist_ok=True)

    # 1. 导出 MD
    out_md = os.path.join(daily_snapshot_dir, f"bilibili_report_{date_str}_{time_str}.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(f"# 📺 Bilibili 每日数据看板 | {date_str} ({now.strftime('%H:%M')})\n\n## 🤖 AI 点评 ({used_model})\n{ai_sum}\n\n## 原始数据\n{raw_txt}")
    
    # 2. 导出 JS (提供最新数据给 Dashboard)
    report_data = {**struct_data, 'date':date_str, 'watch_time':watch_time, 'ai_summary':ai_sum, 'ai_model': used_model}
    js_content = f"var REPORT_DATA = {json.dumps(report_data, ensure_ascii=False)};"
    
    # 始终更新当前最新数据
    with open(os.path.join(daily_snapshot_dir, "latest_report.js"), "w", encoding="utf-8") as f: 
        f.write(js_content)
    
    # 【新增】导出版本化数据文件
    version_js_name = f"data_{time_str}.js"
    with open(os.path.join(daily_snapshot_dir, version_js_name), "w", encoding="utf-8") as f:
        f.write(js_content)

    # 【新增】更新 manifest.js 清单
    manifest_path = os.path.join(daily_snapshot_dir, "manifest.js")
    all_reports = []
    if os.path.exists(manifest_path):
        try:
            # 读取并解析已有列表，兼容 const 和 var
            with open(manifest_path, "r", encoding="utf-8") as f:
                c = f.read().strip()
                c = c.replace("const ALL_REPORTS = ", "").replace("var ALL_REPORTS = ", "").rstrip(";")
                all_reports = json.loads(c)
        except: pass
    
    # 添加新记录（去重）
    new_entry = {"time": now.strftime("%H:%M"), "file": version_js_name, "isLatest": True}
    for item in all_reports: item["isLatest"] = False
    if not any(r['time'] == new_entry['time'] for r in all_reports):
        all_reports.append(new_entry)
    
    all_reports.sort(key=lambda x: x['time'], reverse=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(f"var ALL_REPORTS = {json.dumps(all_reports, ensure_ascii=False)};")

    # 3. 更新趋势图
    trend_file = os.path.join(DATA_DIR, "trend_history.json")
    trends = []
    if os.path.exists(trend_file):
        with open(trend_file, "r") as f: trends = json.load(f)
    short_date = date_str[-5:]
    if trends and trends[-1]["date"] == short_date: trends[-1]["minutes"] = min_watched
    else: trends.append({"date": short_date, "minutes": min_watched})
    with open(trend_file, "w") as f: json.dump(trends[-14:], f)
    with open(os.path.join(daily_snapshot_dir, "time_trend.js"), "w") as f:
        f.write(f"var TIME_TREND = {json.dumps(trends[-14:])};")

    # 4. 拷贝 Web 套件
    for asset in ["index.html", "styles.css", "app.js"]:
        src = os.path.join(WORK_DIR, asset)
        if os.path.exists(src): shutil.copy2(src, os.path.join(daily_snapshot_dir, asset))
    
    # 【新增】同步所有历史快照的 UI (One-time or persistent Sync)
    sync_legacy_reports()

    print(f"✅ 任务完成！存档已归档：{os.path.basename(out_md)}")
    send_notification("B站早报已就绪 ✅", f"{struct_data['user_name']}，您今日的回顾已出炉！")
    subprocess.run(["open", os.path.join(daily_snapshot_dir, "index.html")])

def sync_legacy_reports():
    """遍历所有历史日期文件夹，同步最新的 UI 套件并修正变量声明"""
    notes_base = os.path.join(WORK_DIR, "daily_notes")
    if not os.path.exists(notes_base): return
    
    assets = ["index.html", "styles.css", "app.js"]
    for date_dir in os.listdir(notes_base):
        dp = os.path.join(notes_base, date_dir)
        if not os.path.isdir(dp): continue
        
        # 同步静态资源
        for a in assets:
            src = os.path.join(WORK_DIR, a)
            if os.path.exists(src):
                try: shutil.copy2(src, os.path.join(dp, a))
                except: pass
        
        # 修正历史 JS 文件中的声明以支持动态重载 (const -> var)
        for f in os.listdir(dp):
            if f.endswith(".js"):
                fp = os.path.join(dp, f)
                try:
                    with open(fp, "r", encoding="utf-8") as file: content = file.read()
                    if f == "index.html":
                        content = content.replace("styles-v5.css", "styles.css")
                    if "const " in content:
                        content = content.replace("const REPORT_DATA", "var REPORT_DATA")
                        content = content.replace("const ALL_REPORTS", "var ALL_REPORTS")
                        content = content.replace("const TIME_TREND", "var TIME_TREND")
                    with open(fp, "w", encoding="utf-8") as file: file.write(content)
                except: pass

if __name__ == "__main__":
    try: asyncio.run(main())
    except Exception as e: print(f"❌ 运行报错: {e}")

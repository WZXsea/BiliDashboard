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

# ============ 路径常量 ============
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = SCRIPT_DIR
DATA_DIR = os.path.join(WORK_DIR, "data")
CONFIG_FILE = os.path.join(WORK_DIR, "config.yaml")
CRED_DIR = os.path.join(DATA_DIR, "credentials")
CRED_FILE_DEFAULT = os.path.join(DATA_DIR, "bili_credential.json")
CURRENT_CRED_FILE = None


# ============ 通知推送 ============
def send_notification(title, message, sound="Glass"):
    """发送 macOS 原生通知（适用于 Mac，其他系统仅打印）"""
    if platform.system() == "Darwin":
        try:
            script = f'display notification "{message}" with title "{title}" sound name "{sound}"'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        except Exception as e:
            print(f"通知发送失败: {e}")
    else:
        print(f"[通知] {title}: {message}")

# ============ 配置文件管理 ============
def load_config():
    """加载 config.yaml，不存在则引导用户创建"""
    try:
        import yaml
    except ImportError:
        print("❌ 缺少依赖 pyyaml，请先运行: pip install pyyaml")
        sys.exit(1)

    if not os.path.exists(CONFIG_FILE):
        create_config_interactive(yaml)

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config

def create_config_interactive(yaml):
    """交互式引导用户创建配置文件"""
    print("\n" + "="*50)
    print("🎉 欢迎使用 B站早报生成器！首次运行请配置...")
    print("="*50)
    print("\n📝 请输入您的 Kimi AI API Key（用于生成 AI 总结）")
    kimi_key = input("   API Key: ").strip()
    
    print("\n📝 请输入追踪的 UP主（格式: 名称:UID，按回车结束输入）")
    tracked = {}
    while True:
        line = input("   > ").strip()
        if not line: break
        if ":" in line:
            parts = line.split(":", 1)
            try:
                tracked[parts[0].strip()] = int(parts[1].strip())
            except: pass
    
    if not tracked:
        tracked = {"原神": 401742377, "明日方舟": 161775300}
        
    config = {"kimi_api_key": kimi_key, "tracked_uids": tracked}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    print(f"\n✅ 配置已保存至: {CONFIG_FILE}")

# ============ 多账号实现 ============
async def ensure_credential():
    global CURRENT_CRED_FILE
    from bilibili_api import Credential
    os.makedirs(CRED_DIR, exist_ok=True)
    
    accounts = []
    if os.path.exists(CRED_DIR):
        for f in os.listdir(CRED_DIR):
            if f.endswith(".json"):
                fpath = os.path.join(CRED_DIR, f)
                try:
                    mtime = os.path.getmtime(fpath)
                    with open(fpath, "r") as jf:
                        c_data = json.load(jf)
                        accounts.append({
                            "name": c_data.get("uname", "未知用户"),
                            "uid": c_data.get("dedeuserid", "未知"),
                            "path": fpath, "mtime": mtime
                        })
                except: continue

    accounts.sort(key=lambda x: x['mtime'], reverse=True)
    
    if not accounts:
        print("🔐 未检测到登录凭据，需要扫码登录...")
        CURRENT_CRED_FILE = await qrcode_login()
        return get_credential_by_path(CURRENT_CRED_FILE)

    default_acc = accounts[0]
    print("\n" + "="*50)
    print("👤 多账号管理")
    print("="*50)
    for idx, acc in enumerate(accounts, 1):
        print(f"  [{idx}] {acc['name']} (UID: {acc['uid']})")
    print(f"  [N] 扫码添加新账号")
    print(f"  [D] 删除现有账号")
    print(f"  [Q] 退出程序")
    print("-" * 50)
    print(f"⏰ 请输入选项 (10秒超时默认以 {default_acc['name']} 登录)...")

    choice = None
    if sys.stdin.isatty():
        import select
        rlist, _, _ = select.select([sys.stdin], [], [], 10)
        if rlist: choice = sys.stdin.readline().strip().upper()
    
    if choice == 'Q':
        print("\n👋 收到退出指令，脚本已终止,感谢您的使用，希望你今天也要记得做砺行。")
        sys.exit(0)
    elif choice == 'D':
        await delete_account_menu(accounts)
        return await ensure_credential()
    elif choice == 'N':
        CURRENT_CRED_FILE = await qrcode_login()
    elif choice and choice.isdigit():
        sel_idx = int(choice) - 1
        CURRENT_CRED_FILE = accounts[sel_idx]['path'] if 0 <= sel_idx < len(accounts) else default_acc['path']
    else:
        CURRENT_CRED_FILE = default_acc['path']

    os.utime(CURRENT_CRED_FILE, None)
    return get_credential_by_path(CURRENT_CRED_FILE)

async def delete_account_menu(accounts):
    print("\n" + "x"*50 + "\n🗑  删除账号管理\n" + "x"*50)
    for idx, acc in enumerate(accounts, 1):
        print(f"  [{idx}] {acc['name']} (UID: {acc['uid']})")
    print("  [B] 返回主菜单")
    choice = input("👉 请输入要删除的账号编号: ").strip().upper()
    if choice != 'B' and choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(accounts):
            confirm = input(f"❗ 确定删除 {accounts[idx]['name']}？(y/n): ").lower()
            if confirm == 'y':
                os.remove(accounts[idx]['path'])
                print("✅ 已删除。")
                await asyncio.sleep(1)

def get_credential_by_path(path):
    from bilibili_api import Credential
    if path and os.path.exists(path):
        with open(path, "r") as f:
            c = json.load(f)
            return Credential(sessdata=c.get('sessdata',''), bili_jct=c.get('bili_jct',''), buvid3=c.get('buvid3',''), dedeuserid=c.get('dedeuserid',''))
    return None

async def qrcode_login():
    print("\n正在生成登录二维码...")
    async with httpx.AsyncClient(verify=False) as client:
        res = await client.get("https://passport.bilibili.com/x/passport-login/web/qrcode/generate")
        qr_data = res.json()["data"]
        qr_url, qr_key = qr_data["url"], qr_data["qrcode_key"]
    
    import qrcode
    qr = qrcode.QRCode(box_size=1, border=1)
    qr.add_data(qr_url)
    qr.print_ascii(invert=True)
    
    print("⏳ 请使用 B站手机端扫码...")
    for _ in range(60):
        await asyncio.sleep(2)
        async with httpx.AsyncClient(verify=False) as client:
            poll = await client.get("https://passport.bilibili.com/x/passport-login/web/qrcode/poll", params={"qrcode_key": qr_key})
            p_data = poll.json()["data"]
            if p_data["code"] == 0:
                uid = poll.cookies.get("DedeUserID")
                # 获取昵称
                async with httpx.AsyncClient(cookies=poll.cookies, verify=False) as c2:
                    nav = await c2.get("https://api.bilibili.com/x/web-interface/nav")
                    uname = nav.json()["data"]["uname"]
                
                cred_data = {**poll.cookies, "uname": uname, "dedeuserid": uid, "sessdata": poll.cookies.get("SESSDATA"), "bili_jct": poll.cookies.get("bili_jct")}
                save_path = os.path.join(CRED_DIR, f"{uid}_{uname}.json")
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(cred_data, f, indent=2, ensure_ascii=False)
                return save_path
    sys.exit(1)

def format_number(num):
    return f"{num/10000:.1f}万" if num >= 10000 else str(num)

async def fetch_data(cred):
    cookies = {"SESSDATA": cred.sessdata, "bili_jct": cred.bili_jct}
    headers = {"User-Agent": "Mozilla/5.0"}
    struct_data = {"history": [], "hot": [], "tech": [], "games": [], "user_name": "同学"}
    raw_texts = []

    async with httpx.AsyncClient(cookies=cookies, headers=headers, verify=False, timeout=30.0) as client:
        # 0. User Info
        nav = await client.get("https://api.bilibili.com/x/web-interface/nav")
        struct_data["user_name"] = nav.json().get("data", {}).get("uname", "同学")
        
        # 1. History
        res = await client.get("https://api.bilibili.com/x/web-interface/history/cursor")
        hist = res.json().get("data", {}).get("list", [])
        total_min = 0
        for i in hist:
            p = i.get("progress", 0)
            total_min += (i.get("duration",0) if p == -1 else p)
        total_min //= 60
        struct_data["history"] = [{ "title": i['title'], "author": i['author_name'], "cover": i['cover'].replace('http:','https:'), "url": f"https://bilibili.com/video/{i['history']['bvid']}"} for i in hist[:8]]
        raw_texts.append(f"昨日观看时长: {total_min}分钟\n历史足迹: " + ", ".join([h['title'] for h in struct_data["history"][:5]]))

        # 2. Hot
        res = await client.get("https://api.bilibili.com/x/web-interface/popular?ps=10")
        hot = res.json().get("data", {}).get("list", [])
        struct_data["hot"] = [{"title": i['title'], "author": i['owner']['name'], "cover": i['pic'].replace('http:','https:'), "url": f"https://bilibili.com/video/{i['bvid']}", "play_count": format_number(i['stat']['view'])} for i in hot[:8]]

        # 3. Tech
        res = await client.get("https://api.bilibili.com/x/web-interface/ranking/v2?rid=188")
        tech = res.json().get("data", {}).get("list", [])
        struct_data["tech"] = [{"title": i['title'], "author": i['owner']['name'], "cover": i['pic'].replace('http:','https:'), "url": f"https://bilibili.com/video/{i['bvid']}", "play_count": format_number(i['stat']['view'])} for i in tech[:8]]

        # 4. Dynamics (Simplified)
        from bilibili_api import user
        for name, uid in TRACKED_UIDS.items():
            u = user.User(uid, credential=cred)
            d_res = await u.get_dynamics_new()
            u_info = await u.get_user_info()
            game_rec = {"name": name, "avatar": u_info.get("face","").replace('http:','https:'), "header": u_info.get("top_photo","").replace('http:','https:'), "posts": []}
            for it in d_res.get("items", [])[:3]:
                mod = it.get("modules", {}).get("module_dynamic", {})
                txt = mod.get("desc", {}).get("text", "新动态")
                game_rec["posts"].append({"text": txt, "time": "近期", "url": f"https://t.bilibili.com/{it.get('id_str','')}"})
            struct_data["games"].append(game_rec)
            raw_texts.append(f"UP主 {name} 近期有新动态。")

    return struct_data, f"{total_min}分钟", total_min, "\n".join(raw_texts)

async def generate_summary(text):
    if not KIMI_API_KEY: return "AI总结未配置"
    try:
        async with httpx.AsyncClient(timeout=45.0, verify=False) as client:
            res = await client.post("https://api.moonshot.cn/v1/chat/completions", headers={"Authorization": f"Bearer {KIMI_API_KEY}"}, json={"model":"kimi-k2.5","messages":[{"role":"system","content":"你是一个B站早报专家"},{"role":"user","content": f"根据以下数据总结: {text}"}]})
            return res.json()["choices"][0]["message"]["content"]
    except: return "AI总结生成失败"

def save_dashboard_data(daily_dir, date_str, watch_time, struct_data, ai_summary):
    data = {"date": date_str, "user_name": struct_data['user_name'], "watch_time": watch_time, "ai_summary": ai_summary, "history": struct_data['history'], "hot": struct_data['hot'], "tech": struct_data['tech'], "games": struct_data['games']}
    with open(os.path.join(daily_dir, "latest_report.js"), "w", encoding="utf-8") as f:
        f.write(f"const REPORT_DATA = {json.dumps(data, ensure_ascii=False)};")

async def main():
    config = load_config()
    global KIMI_API_KEY, TRACKED_UIDS
    KIMI_API_KEY, TRACKED_UIDS = config.get("kimi_api_key"), config.get("tracked_uids", {})
    
    cred = await ensure_credential()
    print("正在抓取数据...")
    struct_data, w_str, w_min, raw_txt = await fetch_data(cred)
    ai_sum = await generate_summary(raw_txt)
    
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    daily_dir = os.path.join(WORK_DIR, "daily_notes", date_str)
    os.makedirs(daily_dir, exist_ok=True)
    
    save_dashboard_data(daily_dir, date_str, w_str, struct_data, ai_sum)
    
    for asset in ["index.html", "styles-v5.css", "app.js"]:
        if os.path.exists(os.path.join(WORK_DIR, asset)):
            shutil.copy2(os.path.join(WORK_DIR, asset), os.path.join(daily_dir, asset))
    
    print(f"✅ 完成！存档目录: {daily_dir}")
    send_notification("B站早报已生成 ✅", f"{struct_data['user_name']}，今日回顾已就绪！", sound="Crystal")
    subprocess.run(["open", os.path.join(daily_dir, "index.html")])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 已退出。")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 错误: {e}")
        send_notification("B站早报报错 ❌", str(e)[:50])
        sys.exit(1)

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
# 无论从何处执行，都以脚本所在目录为准
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = SCRIPT_DIR
DATA_DIR = os.path.join(WORK_DIR, "data")
CONFIG_FILE = os.path.join(WORK_DIR, "config.yaml")
CRED_DIR = os.path.join(DATA_DIR, "credentials")
# 默认向上兼容路径
CRED_FILE_DEFAULT = os.path.join(DATA_DIR, "bili_credential.json")
# 运行时选定的凭据路径（由 ensure_credential 填充）
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
        print("❌ 缺少依赖 pyyaml，请先运行: pip install -r requirements.txt")
        sys.exit(1)

    if not os.path.exists(CONFIG_FILE):
        example_file = os.path.join(WORK_DIR, "config.example.yaml")
        if os.path.exists(example_file):
            print("="*50)
            print("❌ 未找到 config.yaml！")
            print("请先复制配置模板并填入您的信息：")
            print(f"  cp config.example.yaml config.yaml")
            print("然后编辑 config.yaml 填写 API Key 和 UP主 UID")
            print("="*50)
            sys.exit(1)
        else:
            print("="*50)
            print("🎉 欢迎使用 B站早报生成器！")
            print("首次运行，需要进行简单配置...")
            print("="*50)
            create_config_interactive(yaml)

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    return config

def create_config_interactive(yaml):
    """交互式引导用户创建配置文件"""
    print("\n📝 请输入您的 Kimi AI API Key（用于生成 AI 总结）")
    print("   获取地址: https://platform.moonshot.cn/console/api-keys")
    kimi_key = input("   API Key: ").strip()
    if not kimi_key:
        kimi_key = ""  # Allow empty, will skip AI summary
        print("   ⚠️ 未填写 API Key，将跳过 AI 总结功能")

    print("\n📝 请输入您要追踪的 UP主/游戏官号（每行一个，格式: 名称:UID）")
    print("   示例: 原神:401742377")
    print("   输入空行结束:")
    tracked = {}
    while True:
        line = input("   > ").strip()
        if not line:
            break
        if ":" in line:
            parts = line.split(":", 1)
            name = parts[0].strip()
            try:
                uid = int(parts[1].strip())
                tracked[name] = uid
                print(f"   ✅ 已添加: {name} (UID: {uid})")
            except ValueError:
                print(f"   ❌ UID 格式错误: {parts[1]}")
    
    if not tracked:
        tracked = {
            "崩坏：星穹铁道": 1340190821,
            "原神": 401742377,
            "明日方舟": 161775300
        }
        print(f"   ℹ️ 未添加追踪，已使用默认列表: {list(tracked.keys())}")

    config = {
        "kimi_api_key": kimi_key,
        "tracked_uids": tracked
    }

    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    
    print(f"\n✅ 配置已保存至: {CONFIG_FILE}")
    print("   您随时可以编辑此文件来修改设置\n")

# ============ 多账号及登录授权 ============
async def ensure_credential():
    """多账号管理逻辑：询问用户是否切换，并带有 10s 超时默认登入"""
    global CURRENT_CRED_FILE
    from bilibili_api import Credential
    
    os.makedirs(CRED_DIR, exist_ok=True)
    
    # 1. 整理现有账号
    accounts = []
    # 检查新文件夹格式
    if os.path.exists(CRED_DIR):
        for f in os.listdir(CRED_DIR):
            if f.endswith(".json"):
                fpath = os.path.join(CRED_DIR, f)
                try:
                    with open(fpath, "r") as jf:
                        c_data = json.load(jf)
                        uname = c_data.get("uname", "")
                        uid = c_data.get("dedeuserid", "未知UID")
                        
                        # 如果没有昵称（比如旧数据），尝试实时获取一下并更新文件
                        if not uname or uname == "未知用户":
                            print(f"⌛️ 正在查询 UID {uid} 的昵称...")
                            uname = await fetch_uname_live(c_data.get("sessdata"), c_data.get("bili_jct"))
                            if uname:
                                c_data["uname"] = uname
                                with open(fpath, "w", encoding="utf-8") as wf:
                                    json.dump(c_data, wf, indent=2, ensure_ascii=False)

                        accounts.append({
                            "name": uname or f"用户_{uid}",
                            "uid": uid,
                            "path": fpath
                        })
                except: continue
    
    # 检查是否有旧路径下的凭据需要迁移
    if os.path.exists(CRED_FILE_DEFAULT) and not accounts:
        print("发现旧版凭据，正在迁移至多账号管理目录...")
        try:
            with open(CRED_FILE_DEFAULT, "r") as f:
                c = json.load(f)
                uid = c.get('dedeuserid', 'unknown')
                print(f"⌛️ 正在查询 UID {uid} 的昵称...")
                uname = await fetch_uname_live(c.get("sessdata"), c.get("bili_jct"))
                if uname: c["uname"] = uname
                
                new_name = f"{uid}_{uname or 'legacy'}.json"
                new_path = os.path.join(CRED_DIR, new_name)
                # 先写入新文件再删旧文件
                with open(new_path, "w", encoding="utf-8") as wf:
                    json.dump(c, wf, indent=2, ensure_ascii=False)
                os.remove(CRED_FILE_DEFAULT)
                accounts.append({"name": uname or "已迁移用户", "uid": uid, "path": new_path})
        except Exception as e:
            print(f"⚠️ 迁移失败: {e}")

    # 2. 如果没有账号，直接进扫码
    if not accounts:
        print("🔐 未检测到任何登录凭据，需要扫码登录 B站...")
        CURRENT_CRED_FILE = await qrcode_login()
        return get_credential_by_path(CURRENT_CRED_FILE)

    # 3. 超时选择逻辑 (10s)
    default_acc = accounts[0] # 默认第一个（可以改进为上次运行的那个）
    print("\n" + "="*50)
    print("👤 多账号管理")
    print("="*50)
    for idx, acc in enumerate(accounts, 1):
        print(f"  [{idx}] {acc['name']} (UID: {acc['uid']})")
    print(f"  [N] 扫码添加新账号")
    print("-" * 50)
    print(f"⏰ 请按数字选择 (10秒内未输入将默认以 {default_acc['name']} 登录)...")

    choice = None
    if sys.stdin.isatty():
        import select
        rlist, _, _ = select.select([sys.stdin], [], [], 10)
        if rlist:
            choice = sys.stdin.readline().strip().upper()
        else:
            print("\n⏰ 已超时，自动登入默认账号。")
    else:
        # 非交互模式自动默认
        print("非交互终端，跳过询问。")

    # 4. 根据选择处理
    if choice and choice != "":
        if choice == 'N':
            CURRENT_CRED_FILE = await qrcode_login()
        else:
            try:
                sel_idx = int(choice) - 1
                if 0 <= sel_idx < len(accounts):
                    CURRENT_CRED_FILE = accounts[sel_idx]['path']
                else:
                    print("⚠️ 输入无效，使用默认账号。")
                    CURRENT_CRED_FILE = default_acc['path']
            except:
                print("⚠️ 输入解析失败，使用默认账号。")
                CURRENT_CRED_FILE = default_acc['path']
    else:
        CURRENT_CRED_FILE = default_acc['path']

    # 5. 验证选定的账号
    cred = get_credential_by_path(CURRENT_CRED_FILE)
    if not cred:
        print("❌ 凭据读取失败，尝试重新扫码...")
        CURRENT_CRED_FILE = await qrcode_login()
        return get_credential_by_path(CURRENT_CRED_FILE)
        
    # 验证是否有效
    try:
        async with httpx.AsyncClient(
            cookies={"SESSDATA": getattr(cred, "sessdata", ""), "bili_jct": getattr(cred, "bili_jct", "")},
            headers={"User-Agent": "Mozilla/5.0"},
            verify=False, timeout=10.0
        ) as client:
            res = await client.get("https://api.bilibili.com/x/web-interface/nav")
            data = res.json()
            if data.get("code") == 0 and data.get("data", {}).get("isLogin"):
                uname = data["data"].get("uname", "未知")
                print(f"✅ 验证通过! 当前身份: {uname}")
                # 顺便更新下文件里的名字，防止改名
                with open(CURRENT_CRED_FILE, "r") as f:
                    c_data = json.load(f)
                    c_data['uname'] = uname
                with open(CURRENT_CRED_FILE, "w") as f:
                    json.dump(c_data, f, indent=2, ensure_ascii=False)
                return cred
            else:
                print("⚠️ 凭据已过期，需要重新扫码登录...")
                CURRENT_CRED_FILE = await qrcode_login()
                return get_credential_by_path(CURRENT_CRED_FILE)
    except Exception as e:
        print(f"⚠️ 验证异常 ({e})，使用当前凭据继续尝试...")
        return cred

def get_credential_by_path(path):
    from bilibili_api import Credential
    if path and os.path.exists(path):
        with open(path, "r") as f:
            c = json.load(f)
            return Credential(
                sessdata=c.get('sessdata', ''),
                bili_jct=c.get('bili_jct', ''),
                buvid3=c.get('buvid3', ''),
                dedeuserid=c.get('dedeuserid', ''),
                ac_time_value=c.get('ac_time_value', '')
            )
    return None

async def fetch_uname_live(sessdata, bili_jct):
    """通过 sessdata 实时获取用户名"""
    try:
        async with httpx.AsyncClient(
            cookies={"SESSDATA": sessdata, "bili_jct": bili_jct},
            headers={"User-Agent": "Mozilla/5.0"}, verify=False, timeout=10.0
        ) as client:
            res = await client.get("https://api.bilibili.com/x/web-interface/nav")
            return res.json().get("data", {}).get("uname")
    except:
        return None

async def qrcode_login():
    """使用 B站 二维码扫码登录，获取并保存凭据"""
    print("\n" + "="*50)
    print("📱 B站扫码登录")
    print("="*50)
    
    # 1. 获取二维码
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/"
    }
    async with httpx.AsyncClient(verify=False, timeout=15.0, headers=headers) as client:
        res = await client.get("https://passport.bilibili.com/x/passport-login/web/qrcode/generate")
        if res.status_code != 200:
            print(f"❌ 获取二维码失败 (HTTP {res.status_code}): {res.text}")
            sys.exit(1)
        qr_data = res.json().get("data", {})
        qr_url = qr_data.get("url", "")
        qr_key = qr_data.get("qrcode_key", "")
    
    if not qr_url or not qr_key:
        print("❌ 获取二维码失败，请检查网络连接")
        sys.exit(1)
    
    # 2. 生成并在终端/窗口显示二维码
    qr_image_path = os.path.join(DATA_DIR, "login_qr.png")
    is_interactive = sys.stdout.isatty()
    
    try:
        import qrcode
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        # 无论是否交互模式，都保存一份图片备份并尝试打开
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(qr_image_path)
        
        if not is_interactive:
            send_notification("B站早报：需扫码登录 🔐", "检测到未登录或凭据失效，已为您弹出二维码图片，请扫码授权。")
            print(f"\n[后台运行] 已生成二维码图片: {qr_image_path}")
        else:
            print("\n[交互模式] 正在终端显示二维码...")
            # 终端显示（小尺寸）
            qr_terminal = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=1, border=1)
            qr_terminal.add_data(qr_url)
            qr_terminal.make(fit=True)
            qr_terminal.print_ascii(invert=True)

        # 尝试使用系统命令打开图片
        try:
            if platform.system() == "Darwin":
                subprocess.run(["open", qr_image_path], check=False)
            elif platform.system() == "Windows":
                os.startfile(qr_image_path)
            print(f"✅ 已为您自动打开二维码图片，请扫码。")
        except:
            print(f"⚠️ 无法自动打开图片，请手动查看: {qr_image_path}")

    except Exception as e:
        print(f"❌ 二维码生成/显示失败: {e}")
        print(f"🔗 请手动打开此链接扫码: {qr_url}")
    
    print("\n👆 请使用 B站手机客户端扫描二维码")
    print("   等待扫码中...", end="", flush=True)
    
    # 3. 轮询等待扫码结果
    from bilibili_api import Credential
    print("\n" + "="*50)
    print("⏳ 等待扫码中... (请在手机端确认登录)")
    print("="*50)
    
    for _ in range(90):  # 最多等待 180 秒 (2s * 90)
        await asyncio.sleep(2)
        
        async with httpx.AsyncClient(verify=False, timeout=10.0, headers=headers) as client:
            poll_res = await client.get(
                "https://passport.bilibili.com/x/passport-login/web/qrcode/poll",
                params={"qrcode_key": qr_key}
            )
            data = poll_res.json()
            poll_data = data.get("data", {})
            code = poll_data.get("code", -1)
            msg = poll_data.get("message", "未知状态")
            
            if code == 0:
                # 登录成功！
                print(f"\n\n🎉 登录成功！(状态码: {code})")
                
                # 从 URL 参数提取凭据
                url_str = poll_data.get("url", "")
                from urllib.parse import urlparse, parse_qs
                parsed = parse_qs(urlparse(url_str).query)
                
                # 优先从本地 Cookie 获取，如果没有则从跳转 URL 获取
                cred_data = {
                    "sessdata": poll_res.cookies.get("SESSDATA", parsed.get("SESSDATA", [""])[0]),
                    "bili_jct": poll_res.cookies.get("bili_jct", parsed.get("bili_jct", [""])[0]),
                    "buvid3": poll_res.cookies.get("buvid3", ""),
                    "dedeuserid": poll_res.cookies.get("DedeUserID", parsed.get("DedeUserID", [""])[0]),
                    "ac_time_value": poll_res.cookies.get("ac_time_value", ""),
                    "refresh_token": poll_data.get("refresh_token", "")
                }
                f
                # 保存凭据
                os.makedirs(CRED_DIR, exist_ok=True)
                uid = cred_data["dedeuserid"]
                # 尝试获取用户名用于命名
                uname = "Unknown"
                async with httpx.AsyncClient(cookies={"SESSDATA": cred_data["sessdata"], "bili_jct": cred_data["bili_jct"]}, verify=False) as client:
                    try:
                        n_res = await client.get("https://api.bilibili.com/x/web-interface/nav")
                        uname = n_res.json().get("data", {}).get("uname", f"User_{uid}")
                    except: pass
                
                cred_data['uname'] = uname
                save_path = os.path.join(CRED_DIR, f"{uid}_{uname}.json")
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(cred_data, f, indent=2, ensure_ascii=False)
                
                print(f"   凭据已分账户保存至: {save_path}")
                return save_path
            elif code == 86038:
                print(f"\n\n❌ 二维码已过期 (状态码: {code})")
                sys.exit(1)
            elif code == 86090:
                print(f"\r⏳ [状态: 已扫码，等待确认] {msg}   ", end="", flush=True)
            elif code == 86101:
                print(f"\r⏳ [状态: 等待扫码...] {msg}       ", end="", flush=True)
            else:
                print(f"\r⏳ [状态: {code}] {msg}           ", end="", flush=True)
    
    print("\n\n❌ 等待超时，请重新运行程序")
    sys.exit(1)

def get_cookies():
    cred_path = CURRENT_CRED_FILE
    if cred_path and os.path.exists(cred_path):
        with open(cred_path, "r") as f:
            c = json.load(f)
            return {
                "SESSDATA": c.get("sessdata", ""),
                "bili_jct": c.get("bili_jct", ""),
                "buvid3": c.get("buvid3", ""),
                "DedeUserID": c.get("dedeuserid", ""),
                "ac_time_value": c.get("ac_time_value", "")
            }
    return {}

def get_credential():
    return get_credential_by_path(CURRENT_CRED_FILE)

def format_number(num):
    if num >= 10000:
        return f"{num/10000:.1f}万"
    return str(num)

async def fetch_data():
    cookies = get_cookies()
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    watch_time_str = "0分钟"
    user_nickname = "同学"
    struct_data = {
        "user_name": user_nickname,
        "history": [],
        "hot": [],
        "tech": [],
        "games": [],
        "raw_text_for_ai": ""
    }


    raw_texts = []
    
    async with httpx.AsyncClient(cookies=cookies, headers=headers, verify=False, timeout=30.0) as client:
        # 0. 用户信息
        try:
            print("正在获取用户信息...")
            res_nav = await client.get("https://api.bilibili.com/x/web-interface/nav")
            nav_data = res_nav.json().get("data", {})
            if nav_data:
                user_nickname = nav_data.get("uname", "同学")
                struct_data["user_name"] = user_nickname
            print(f"获取到用户: {user_nickname}")
        except Exception as e: 
            print(f"获取用户信息失败: {e}")
            pass

        # 1. 历史足迹
        try:
            print("正在获取历史足迹...")
            res = await client.get("https://api.bilibili.com/x/web-interface/history/cursor")
            hist = res.json().get("data", {}).get("list", [])
            print(f"获取到 {len(hist)} 条历史记录")
            if hist:
                total_time_sec = 0
                for item in hist:
                    prog = item.get("progress", 0)
                    dur = item.get("duration", 0)
                    if prog == -1: total_time_sec += dur
                    elif prog > 0: total_time_sec += prog
                
                hours = total_time_sec // 3600
                minutes = (total_time_sec % 3600) // 60
                watch_time_str = f"{hours}小时 {minutes}分钟" if hours > 0 else f"{minutes}分钟"
                
                for i in hist[:8]:
                    struct_data["history"].append({
                        "title": i.get('title', '未知'),
                        "author": i.get('author_name', '未知'),
                        "cover": i.get('cover', '').replace('http:', 'https:'),
                        "url": f"https://www.bilibili.com/video/{i.get('history', {}).get('bvid', '')}"
                    })
                
                hist_str = "\n".join([f"- {i['title']}" for i in struct_data["history"][:8]])
                raw_texts.append(f"【昨日总观看时长】：{watch_time_str}\n【足迹】：\n{hist_str}")
        except Exception as e:
            raw_texts.append(f"获取历史足迹失败: {e}")

        # 2. 全站热门
        try:
            res = await client.get("https://api.bilibili.com/x/web-interface/popular?pn=1&ps=10")
            hot = res.json().get("data", {}).get("list", [])
            for i in hot[:8]:
                struct_data["hot"].append({
                    "title": i.get('title', ''),
                    "author": i.get('owner', {}).get('name', ''),
                    "cover": i.get('pic', '').replace('http:', 'https:'),
                    "url": f"https://www.bilibili.com/video/{i.get('bvid', '')}",
                    "play_count": format_number(i.get('stat', {}).get('view', 0))
                })
            hot_str = "\n".join([f"- {i['title']}" for i in struct_data["hot"][:5]])
            raw_texts.append(f"\n【全站近期热门】：\n{hot_str}")
        except: pass

        # 3. 科技区热门
        try:
            res = await client.get("https://api.bilibili.com/x/web-interface/ranking/v2?rid=188")
            tech = res.json().get("data", {}).get("list", [])
            for i in tech[:8]:
                struct_data["tech"].append({
                    "title": i.get('title', ''),
                    "author": i.get('owner', {}).get('name', ''),
                    "cover": i.get('pic', '').replace('http:', 'https:'),
                    "url": f"https://www.bilibili.com/video/{i.get('bvid', '')}",
                    "play_count": format_number(i.get('stat', {}).get('view', 0))
                })
            tech_str = "\n".join([f"- {i['title']}" for i in struct_data["tech"][:3]])
            raw_texts.append(f"\n【科技区热门】：\n{tech_str}")
        except: pass

        # 4. 关注的账号动态 (最近24小时)
        now_ts = int(time.time())
        day_sec = 24 * 3600
        raw_texts.append("\n【关注账号24小时内动态】")
        print(f"开始获取关注UP主动态...")
        
        from bilibili_api import user
        cred = get_credential()
        
        for name, uid in TRACKED_UIDS.items():
            print(f"正在处理 UP主: {name} (UID: {uid})...")
            game_record = {"name": name, "posts": [], "videos": [], "avatar": "", "header": ""}

            try:
                u = user.User(uid, credential=cred)
                # 获取用户信息（头像、头图）
                print(f"  正在获取 {name} 的用户信息...")
                uinfo = await u.get_user_info()
                avatar = (uinfo.get("face", "") or "").replace('http:', 'https:')
                header = uinfo.get("top_photo", "")
                if header and not header.startswith("http"):
                    header = "https://i0.hdslb.com/" + header
                game_record["avatar"] = avatar
                game_record["header"] = header.replace('http:', 'https:')
                
                # 1. 获取动态列表
                print(f"  正在获取 {name} 的近期动态...")
                res_dyn = await u.get_dynamics_new()
                items = res_dyn.get("items", [])
                print(f"  获取到 {len(items)} 条动态")
                
                game_posts = []
                seen_bvids = set() # 用于去重
                
                for item in items:
                    auth = item.get("modules", {}).get("module_author") or {}
                    pub_ts = auth.get("pub_ts", 0)
                    try:
                        pub_ts = int(pub_ts)
                    except:
                        pub_ts = 0
                    if now_ts - pub_ts > day_sec: continue
                    
                    mod_dyn = item.get("modules", {}).get("module_dynamic") or {}
                    desc_obj = mod_dyn.get("desc") or {}
                    desc = desc_obj.get("text", "")
                    
                    cover = ""
                    bvid = ""
                    major = mod_dyn.get("major") or {}
                    if major:
                        if 'opus' in major:
                            opus = major.get('opus') or {}
                            if not desc:
                                opus_sum = opus.get('summary') or {}
                                desc = opus_sum.get('text', '') or opus.get('title', '')
                            if opus.get('pics'): cover = opus['pics'][0].get('url', '')
                        elif 'archive' in major:
                            archive = major.get('archive') or {}
                            if not desc: desc = archive.get('title', '')
                            cover = archive.get('cover', '')
                            bvid = archive.get('bvid', '')
                            if bvid: seen_bvids.add(bvid)
                        elif 'article' in major:
                            article = major.get('article') or {}
                            if not desc: desc = article.get('title', '')
                            if article.get('covers'): cover = article['covers'][0]
                        elif 'draw' in major:
                            draw = major.get('draw') or {}
                            if draw.get('items'): cover = draw['items'][0].get('src', '')
                    
                    if not desc: desc = "分享了动态/视频"
                    if "恭喜@" in desc and "中奖" in desc: continue
                        
                    id_str = item.get("id_str", "")
                    url = f"https://t.bilibili.com/{id_str}" if id_str else f"https://space.bilibili.com/{uid}/dynamic"
                    game_posts.append({
                        "text": desc,
                        "cover": (cover or "").replace('http:', 'https:'),
                        "url": url,
                        "time": datetime.datetime.fromtimestamp(pub_ts).strftime("%m-%d %H:%M")
                    })


                # 2. 获取昨日视频
                print(f"  正在获取 {name} 的昨日投稿视频...")
                try:
                    res_vids = await u.get_videos(ps=10)
                    vlist = res_vids.get("list", {}).get("vlist", [])
                    for v in vlist:
                        v_created = v.get("created", 0)
                        if now_ts - v_created > day_sec: continue
                        v_bvid = v.get("bvid", "")
                        if v_bvid in seen_bvids: continue
                        
                        video_item = {
                            "text": v.get('title', ''),
                            "author": name,
                            "author_avatar": avatar,
                            "cover": v.get('pic', '').replace('http:', 'https:'),
                            "url": f"https://www.bilibili.com/video/{v_bvid}",
                            "time": datetime.datetime.fromtimestamp(v_created).strftime("%m-%d %H:%M")
                        }
                        game_record["videos"].append(video_item)

                        seen_bvids.add(v_bvid)
                except Exception as ve:
                    print(f"    ⚠️ 视频抓取跳过: {ve}")


                game_posts.sort(key=lambda x: x['time'], reverse=True)
                game_record["posts"] = game_posts
                if game_posts:

                    briefs = [p['text'][:60].replace('\n', ' ') for p in game_posts]
                    raw_texts.append(f"- **{name}**: 共有 {len(game_posts)} 条新动态。简报：{briefs}")
                else:
                    raw_texts.append(f"- **{name}**: 过去24小时无更新。")
                    
            except Exception as e:
                print(f"  ❌ {name} 获取失败: {type(e).__name__} - {e}")
                raw_texts.append(f"- **{name}**: 获取失败 ({type(e).__name__} - {e})")
            
            struct_data["games"].append(game_record)
    
    struct_data["raw_text_for_ai"] = "\n".join(raw_texts)
    return struct_data, watch_time_str, total_time_sec // 60

async def generate_summary(raw_text):
    prompt = f"""
你是我专属的“B站首席早报撰写官”。我提供给了我昨日的足迹、全站热榜、科技热榜以及关注的游戏近24小时动态。
请写一段**非常简短、风趣幽默的AI开场点评**（300字以内），作为我早报看板的每日寄语。
1. 点评一下我昨日看的视频口味或者观看时长。
2. 一句话总结全站或科技区今天最大的看点。
3. 一句话提醒游戏官方是否有大新闻（如果有的话）。

底层数据如下（供分析参考）：
{raw_text}
"""
    headers = {"Authorization": f"Bearer {KIMI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "kimi-k2.5",
        "messages": [
            {"role": "system", "content": "你是一个专业的B站早报撰写官"},
            {"role": "user", "content": prompt}
        ]
    }
    
    try:
        async with httpx.AsyncClient(timeout=45.0, verify=False) as client:
            res = await client.post("https://api.moonshot.cn/v1/chat/completions", json=payload, headers=headers)
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"]
                return content
            else:
                try:
                    err_json = res.json()
                    err_msg = err_json.get("error", {}).get("message", "未知错误")
                    return f"今日摘要生成失败 ({res.status_code}: {err_msg})"
                except:
                    return f"今日摘要生成失败 (HTTP {res.status_code})"
    except Exception as e:
        return f"无法连接到 AI 大模型: {e}"

def save_dashboard_data(daily_dir, date_str, watch_time, struct_data, ai_summary):
    js_content = f"""// AUTO-GENERATED BY BILI DAILY SCRIPT
const REPORT_DATA = {{
    "date": "{date_str}",
    "user_name": "{struct_data['user_name']}",
    "watch_time": "{watch_time}",
    "ai_summary": {json.dumps(ai_summary, ensure_ascii=False)},
    "history": {json.dumps(struct_data['history'], ensure_ascii=False)},
    "hot": {json.dumps(struct_data['hot'], ensure_ascii=False)},
    "tech": {json.dumps(struct_data['tech'], ensure_ascii=False)},
    "games": {json.dumps(struct_data['games'], ensure_ascii=False)}


}};
"""
    js_file = os.path.join(daily_dir, "latest_report.js")
    with open(js_file, "w", encoding="utf-8") as f:
        f.write(js_content)

def update_and_save_trend(daily_dir, date_str, today_minutes):
    trend_file = os.path.join(DATA_DIR, "trend_history.json")
    trends = []
    if os.path.exists(trend_file):
        try:
            with open(trend_file, "r") as f:
                trends = json.load(f)
        except: pass
    
    short_date = date_str[-5:]
    if trends and trends[-1]["date"] == short_date:
        trends[-1]["minutes"] = today_minutes
    else:
        trends.append({"date": short_date, "minutes": today_minutes})
    
    trends = trends[-14:]
    with open(trend_file, "w") as f:
        json.dump(trends, f)
        
    trend_js = f"const TIME_TREND = {json.dumps(trends)};"
    with open(os.path.join(daily_dir, "time_trend.js"), "w") as f:
        f.write(trend_js)

async def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # 加载配置
    config = load_config()
    global KIMI_API_KEY, TRACKED_UIDS
    KIMI_API_KEY = config.get("kimi_api_key", "")
    TRACKED_UIDS = config.get("tracked_uids", {})
    
    print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] >>> B站早报脚本开始启动")
    print(f"   追踪列表: {list(TRACKED_UIDS.keys())}")
    
    # 确保登录凭据有效
    await ensure_credential()
    
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 正在连接 B站 API 获取原始数据...")
    struct_data, watch_time, min_watched = await fetch_data()
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 数据抓取完成，共获取到 历史:{len(struct_data['history'])}条, 全站热门:{len(struct_data['hot'])}条")
    
    if KIMI_API_KEY:
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 正在请求 Kimi-2.5 深度总结数据...")
        ai_summary = await generate_summary(struct_data["raw_text_for_ai"])
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] AI 总结生成成功！")
    else:
        ai_summary = "*AI 总结功能未配置（请在 config.yaml 中填写 kimi_api_key）*"
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ⚠️ 跳过 AI 总结（未配置 API Key）")
    
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 创建每日隔离的 snapshot 目录
    daily_snapshot_dir = os.path.join(WORK_DIR, "daily_notes", date_str)
    os.makedirs(daily_snapshot_dir, exist_ok=True)
    
    out_md = os.path.join(daily_snapshot_dir, f"B站早报_{date_str}.md")
    
    # 保存文本备份
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# Kimi 每日点评\n" + ai_summary + "\n\n---\n原始数据备份:\n" + struct_data["raw_text_for_ai"])
        
    print(f"MD存档已生成: {out_md}")
    
    # 保存可视化数据到 daily目录
    save_dashboard_data(daily_snapshot_dir, date_str, watch_time, struct_data, ai_summary)
    update_and_save_trend(daily_snapshot_dir, date_str, min_watched)
    
    # 拷贝核心展示套件到今日快照文件夹
    for asset in ["index.html", "styles-v5.css", "app.js"]:
        src = os.path.join(WORK_DIR, asset)
        dst = os.path.join(daily_snapshot_dir, asset)
        if os.path.exists(src):
            shutil.copy2(src, dst)

            
    user_name = struct_data.get('user_name', '同学')
    print(f"✅ Dashboard 日记快照已归档至: {daily_snapshot_dir}")
    
    # 🔔 发送 macOS 通知
    send_notification(
        "B站早报已生成 ✅",
        f"{user_name}，你的 {date_str} B站回顾已就绪！观看时长：{watch_time}"
    )
    
    # 🚀 自动打开 Dashboard
    target_index = os.path.join(daily_snapshot_dir, "index.html")
    if os.path.exists(target_index):
        print(f"🚀 正在为您打开 Dashboard: {target_index}")
        subprocess.run(["open", target_index])


if __name__ == "__main__":
    asyncio.run(main())

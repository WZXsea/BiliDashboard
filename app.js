document.addEventListener("DOMContentLoaded", () => {
    // 1. 数据驱动渲染
    if (typeof REPORT_DATA !== "undefined") {
        renderDashboard(REPORT_DATA);
        updateSubMenu(REPORT_DATA);
        initReportSwitcher();
    }

    // 2. 状态记忆与可见性控制
    const filters = [
        { id: "toggle-summary", section: "summary" },
        { id: "toggle-trend",   section: "trend" },
        { id: "toggle-history", section: "history" },
        { id: "toggle-hot",     section: "hot" },
        { id: "toggle-tech",    section: "tech" },
        { id: "toggle-dynamics",section: "dynamics" }
    ];

    filters.forEach(f => {
        const toggle = document.getElementById(f.id);
        const section = document.getElementById(f.section);
        if (toggle && section) {
            const saved = localStorage.getItem(f.id);
            if (saved === "false") {
                toggle.checked = false;
                section.classList.add("hidden-section");
            }
            toggle.addEventListener("change", (e) => {
                section.classList.toggle("hidden-section", !e.target.checked);
                localStorage.setItem(f.id, e.target.checked);
            });
        }
    });

    // 3. 全局统一卡片模板 (B站原生风格：底色透明，文字外挂)
    function createStandardCard(v) {
        return `
            <a href="${v.url}" target="_blank" class="media-item">
                <div class="media-cover-wrapper">
                    <img src="${v.cover}" class="media-cover" alt="${v.title}" loading="lazy">
                    <div class="media-overlay">
                        <div class="overlay-left">
                            ${v.play_count ? `<span><ion-icon name="play-circle-outline"></ion-icon> ${v.play_count}</span>` : ''}
                            ${v.danmaku ? `<span><ion-icon name="chatbox-ellipses-outline"></ion-icon> ${v.danmaku}</span>` : ''}
                        </div>
                        <div class="overlay-right">
                            <span>${v.duration || '--:--'}</span>
                        </div>
                    </div>
                </div>
                <div class="media-info">
                    <div class="media-title">${v.title}</div>
                    <div class="media-meta">
                        <span class="author">@${v.author}</span>
                        <span class="pub-date">${v.pub_date || ''}</span>
                    </div>
                </div>
            </a>
        `;
    }

    function renderDashboard(data) {
        document.getElementById("user-name").textContent = data.user_name || "用户";
        const avatar = document.getElementById("user-avatar-initial");
        if (avatar) avatar.textContent = (data.user_name || "U")[0].toUpperCase();
        document.getElementById("current-date").textContent = `${data.user_name || "用户"} 一日动态`;
        
        const summary = document.getElementById("summary-content");
        if (summary && data.ai_summary) summary.innerHTML = marked.parse(data.ai_summary);

        const modelTag = document.getElementById("ai-model-tag");
        if (modelTag && data.ai_model) {
            modelTag.textContent = data.ai_model.split('/').pop().toUpperCase().replace('DEEPSEEK-', '').replace('GPT-4O-', '4O-');
        }

        if (typeof TIME_TREND !== "undefined") {
            const ctx = document.getElementById('trendChart');
            if (ctx) {
                if (window.myChart) window.myChart.destroy();
                window.myChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: TIME_TREND.map(t => t.date),
                        datasets: [{ label: '观看分钟', data: TIME_TREND.map(t => t.minutes), borderColor: '#ff758c', tension: 0.4 }]
                    },
                    options: { responsive: true, maintainAspectRatio: false }
                });
            }
        }

        // 全板块同步渲染
        const sections = [
            { id: "history-list", data: data.history, badge: false },
            { id: "hot-list",     data: data.hot,     badge: true },
            { id: "tech-list",    data: data.tech,    badge: true }
        ];

        sections.forEach(s => {
            const el = document.getElementById(s.id);
            if (el && s.data) {
                el.innerHTML = s.data.map(v => createStandardCard(v)).join("");
            }
        });

        // 动态区渲染
        const dynamics = document.getElementById("dynamics-nav-wrapper") ? document.getElementById("game-dynamics-list") : null;
        const targetDynamics = dynamics || document.getElementById("dynamics");
        
        const getSafeId = (name) => 'game-' + name.replace(/[^\w\u4e00-\u9fa5]/g, '_');

        if (targetDynamics && data.games) {
            targetDynamics.innerHTML = data.games.map(g => {
                const safeId = getSafeId(g.name);
                return `
                <div id="${safeId}" data-up-name="${g.name}" class="up-section glass-card">
                    <div class="up-header-wrapper">
                        <img src="${g.header}" class="up-header-img">
                        <div class="up-header-overlay">
                            <a href="https://space.bilibili.com/${g.uid}" target="_blank" class="up-avatar-link">
                                <img src="${g.avatar}" class="up-avatar">
                            </a>
                            <div class="up-info-text">
                                <h3 class="up-title">${g.name}</h3>
                                <div class="up-tab-btns">
                                    <button class="up-tab-btn active" data-tab="posts">
                                        <ion-icon name="chatbubble-ellipses-outline"></ion-icon> 
                                        动态 <span class="tab-count">${g.posts.length}</span>
                                    </button>
                                    <button class="up-tab-btn" data-tab="videos">
                                        <ion-icon name="play-circle-outline"></ion-icon> 
                                        投稿 <span class="tab-count">${g.videos ? g.videos.length : 0}</span>
                                    </button>
                                </div>
                            </div>
                            <div class="up-meta">
                                <div class="collapse-btn">
                                    <ion-icon name="chevron-up-outline"></ion-icon>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="up-integrated-body">
                        <!-- 动态视图 -->
                        <div class="up-tab-content active" data-content="posts">
                            <div class="up-post-list horizontal-scroll">
                                ${g.posts.length > 0 ? g.posts.map(p => `
                                    <div class="up-post-card">
                                        ${p.pics && p.pics.length > 1 ? `
                                            <div class="up-post-pics-grid grid-${p.pics.length > 4 ? 3 : (p.pics.length === 4 ? 2 : p.pics.length)}">
                                                ${p.pics.slice(0, 9).map(pic => `<img src="${pic}" class="grid-pic" loading="lazy">`).join('')}
                                            </div>
                                        ` : (p.cover ? `<img src="${p.cover}" class="up-post-full-cover" loading="lazy">` : '')}
                                        <div class="up-post-main">
                                            <div class="up-post-scrollable">
                                                <div class="up-post-text">${p.text}</div>
                                            </div>
                                            <div class="up-post-bottom">
                                                <div class="up-post-time">
                                                    <ion-icon name="time-outline"></ion-icon>
                                                    <span>${p.time}</span>
                                                </div>
                                                <a href="${p.url}" target="_blank" class="view-original-link">
                                                    <ion-icon name="link-outline"></ion-icon>
                                                    查看原贴
                                                </a>
                                            </div>
                                        </div>
                                    </div>
                                `).join("") : `
                                    <div class="up-empty-state">
                                        <ion-icon name="moon-outline"></ion-icon>
                                        <p>过去 24 小时没有发布新动态</p>
                                    </div>
                                `}
                            </div>
                        </div>

                        <!-- 投稿视图 -->
                        <div class="up-tab-content" data-content="videos">
                            <div class="mini-video-list horizontal-scroll">
                                ${g.videos && g.videos.length > 0 ? g.videos.map(v => `
                                    <a href="https://www.bilibili.com/video/${v.bvid}" target="_blank" class="mini-video-item">
                                        <img src="${v.cover}" class="mini-video-thumb">
                                        <div class="mini-video-details">
                                            <div class="mini-video-text">${v.title}</div>
                                            <div class="mini-video-meta">
                                                <span><ion-icon name="play-outline"></ion-icon>${v.play}</span>
                                                <span>${v.time}</span>
                                            </div>
                                        </div>
                                    </a>
                                `).join("") : `
                                    <div class="up-empty-state">
                                        <ion-icon name="videocam-off-outline"></ion-icon>
                                        <p>近期暂无视频投稿</p>
                                    </div>
                                `}
                            </div>
                        </div>
                    </div>
                </div>
            `;
            }).join("");
        }
    }

    // 4. 主题系统：首选系统设置，其次用户记忆
    const themeBtn = document.getElementById("theme-toggle");
    const themeIcon = document.getElementById("theme-icon");
    const systemThemeQuery = window.matchMedia('(prefers-color-scheme: light)');

    function updateTheme(isLight) {
        document.body.classList.toggle("light-theme", isLight);
        themeIcon.setAttribute("name", isLight ? "moon-outline" : "sunny-outline");
        localStorage.setItem("theme_preference", isLight ? "light" : "dark");
    }

    // 初始化逻辑：1. 检查手动记录 2. 检查系统偏好
    const savedTheme = localStorage.getItem("theme_preference");
    if (savedTheme) {
        updateTheme(savedTheme === "light");
    } else {
        updateTheme(systemThemeQuery.matches);
    }

    // 实时监听系统主题变化
    systemThemeQuery.addEventListener("change", (e) => {
        if (!localStorage.getItem("theme_preference")) {
            updateTheme(e.matches);
        }
    });

    themeBtn.addEventListener("click", () => {
        const currentlyLight = document.body.classList.contains("light-theme");
        updateTheme(!currentlyLight);
    });

    // 5. 版本切换器
    function initReportSwitcher() {
        const sel = document.getElementById("report-version-select");
        if (sel && typeof ALL_REPORTS !== "undefined") {
            sel.innerHTML = ALL_REPORTS.map(r => `<option value="${r.file}" ${r.isLatest ? 'selected' : ''}>${r.time}</option>`).join("");
            sel.addEventListener("change", (e) => {
                const s = document.createElement("script");
                s.src = e.target.value;
                s.onload = () => { 
                    if (typeof REPORT_DATA !== "undefined") {
                        renderDashboard(REPORT_DATA); 
                        updateSubMenu(REPORT_DATA); // 强制同步更新 UP 主二级菜单
                    }
                };
                document.body.appendChild(s);
            });
        }
    }

    function updateSubMenu(data) {
        const getSafeId = (name) => 'game-' + name.replace(/[^\w\u4e00-\u9fa5]/g, '_');
        const sub = document.getElementById("dynamics-sub-menu");
        if (sub && data.games) sub.innerHTML = data.games.map(g => {
            const safeId = getSafeId(g.name);
            return `<a href="#${safeId}" data-target="${safeId}" class="sub-nav-item">${g.name}</a>`;
        }).join("");
    }

    // 6. 交互：UP 部分折叠与 Tab 切换控制
    document.addEventListener("click", (e) => {
        // 折叠控制
        const collapseBtn = e.target.closest(".collapse-btn");
        if (collapseBtn) {
            const section = collapseBtn.closest(".up-section");
            if (section) {
                section.classList.toggle("collapsed");
                const icon = collapseBtn.querySelector("ion-icon");
                if (icon) {
                    const isCollapsed = section.classList.contains("collapsed");
                    icon.setAttribute("name", isCollapsed ? "chevron-down-outline" : "chevron-up-outline");
                }
            }
            return;
        }

        // Tab 切换控制
        const tabBtn = e.target.closest(".up-tab-btn");
        if (tabBtn) {
            const tabName = tabBtn.dataset.tab;
            const section = tabBtn.closest(".up-section");
            if (section) {
                // 切换按钮状态
                section.querySelectorAll(".up-tab-btn").forEach(b => b.classList.remove("active"));
                tabBtn.classList.add("active");

                // 切换内容显隐
                section.querySelectorAll(".up-tab-content").forEach(c => {
                    c.classList.toggle("active", c.dataset.content === tabName);
                });
            }
            return;
        }

        // 全局点击关闭设置菜单
        if (!settingsBtn.contains(e.target) && !settingsPopup.contains(e.target)) {
            settingsPopup.classList.remove("active");
        }
    });
    
    // 7. 设置菜单交互逻辑
    const settingsBtn = document.getElementById("settings-btn");
    const settingsPopup = document.getElementById("settings-popup");
    
    if (settingsBtn && settingsPopup) {
        settingsBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            const isActive = settingsPopup.classList.toggle("active");
        if (isActive) {
            settingsPopup.scrollTop = 0;
        }
        });

        // 全局点击关闭
        document.addEventListener("click", () => {
            settingsPopup.classList.remove("active");
        });

        // 阻止菜单内部点击关闭
        settingsPopup.addEventListener("click", (e) => e.stopPropagation());

        // 功能 1：一键复制同步指令
        const syncBtn = document.getElementById("run-report-item");
        if (syncBtn) {
            syncBtn.addEventListener("click", () => {
                const cmd = "python3 bili_daily_report.py";
                navigator.clipboard.writeText(cmd).then(() => {
                    alert("🚀 同步指令已成功复制到剪贴板！\n请打开您的终端 (Terminal) 粘贴运行该指令。");
                }).catch(() => {
                    alert("复制失败，请手动运行: " + cmd);
                });
                settingsPopup.classList.remove("active");
            });
        }

        // 功能 2：修改配置引导
        const configBtn = document.getElementById("open-config-item");
        if (configBtn) {
            configBtn.addEventListener("click", () => {
                alert("⚙️ 配置文件路径：\n项目根目录下的 config.yaml\n\n请使用您的编辑器 (如 VS Code) 打开并修改监听的 UID 后，再次运行同步指令。");
                settingsPopup.classList.remove("active");
            });
        }
    }

    // 8. 全屏图片查看器 (Lightbox) 交互逻辑
    const imageViewerModal = document.getElementById("image-viewer-modal");
    const fullImageElement = document.getElementById("full-image");
    
    if (imageViewerModal && fullImageElement) {
        document.addEventListener("click", (e) => {
            // 匹配所有可点击的图片类
            const clickableImg = e.target.closest(".up-post-full-cover, .grid-pic, .mini-video-thumb");
            
            if (clickableImg) {
                // 仅当点击图片本身时触发
                if (e.target === clickableImg) {
                    imageViewerModal.style.display = "flex";
                    fullImageElement.src = clickableImg.src;
                }
                return;
            }

            // 关闭逻辑：点击背景或关闭按钮
            if (e.target.classList.contains("close-viewer") || e.target === imageViewerModal) {
                imageViewerModal.style.display = "none";
            }
        });
        
        // 按 ESC 键关闭
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                imageViewerModal.style.display = "none";
            }
        });
    }

    // 9. AI 配置助手逻辑
    const aiProviderSelect = document.getElementById("ai-provider-select");
    const aiBaseUrlInput = document.getElementById("ai-base-url-input");
    const aiModelInput = document.getElementById("ai-model-input");
    const aiApiKeyInput = document.getElementById("ai-api-key-input");
    const genYamlBtn = document.getElementById("gen-ai-yaml");

    const AI_PRESETS_DATA = {
        "kimi": { url: "https://api.moonshot.cn/v1", model: "kimi-k2.5" },
        "deepseek": { url: "https://api.deepseek.com/v1", model: "deepseek-chat" },
        "openai": { url: "https://api.openai.com/v1", model: "gpt-4o-mini" }
    };

    if (aiProviderSelect) {
        aiProviderSelect.addEventListener("change", (e) => {
            const preset = AI_PRESETS_DATA[e.target.value];
            if (preset) {
                aiBaseUrlInput.value = preset.url;
                aiModelInput.value = preset.model;
            } else {
                aiBaseUrlInput.value = "";
                aiModelInput.value = "";
            }
        });
    }

    if (genYamlBtn) {
        genYamlBtn.addEventListener("click", () => {
            const provider = aiProviderSelect.value;
            const api_key = aiApiKeyInput.value || "YOUR_API_KEY";
            const base_url = aiBaseUrlInput.value;
            const model = aiModelInput.value;
            
            let yaml = "ai_config:\n";
            if (provider !== "custom") yaml += `  provider: "${provider}"\n`;
            yaml += `  api_key: "${api_key}"\n`;
            if (base_url) yaml += `  base_url: "${base_url}"\n`;
            if (model) yaml += `  model: "${model}"\n`;
            
            navigator.clipboard.writeText(yaml).then(() => {
                alert("📋 已生成配置块并复制到剪贴板！\n\n请将其粘贴并替换 config.yaml 中的 ai_config 部分，然后重新运行抓取脚本。");
            }).catch(() => {
                alert("无法自动复制，请手动配置。");
            });
        });
    }

    // 10. 侧边栏联动 (ScrollSync & ScrollSpy)
    function initScrollSync() {
        const scrollContainer = document.querySelector('.scroll-container');
        const navMenu = document.querySelector('.nav-menu');
        if (!scrollContainer || !navMenu) return;

        function getRelativeOffsetTop(el, container) {
            if (!el || !container) return 0;
            return el.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop;
        }

        function setActiveNavItem(targetId, shouldScroll = false) {
            if (!targetId) return;
            const decodedId = decodeURIComponent(targetId);
            document.querySelectorAll('.nav-item-wrapper, .sub-nav-item').forEach(el => el.classList.remove('active-nav'));

            const pLink = document.querySelector(`.nav-item-wrapper a[href="#${decodedId}"], .nav-item-wrapper a[href="#${targetId}"]`);
            if (pLink) pLink.closest('.nav-item-wrapper').classList.add('active-nav');

            const sLink = document.querySelector(`.sub-nav-item[href="#${targetId}"], .sub-nav-item[href="#${decodedId}"], .sub-nav-item[data-target="${decodedId}"]`);
            if (sLink) {
                sLink.classList.add('active-nav');
                const dynWrapper = document.querySelector('#dynamics-nav-wrapper .nav-item-wrapper');
                if (dynWrapper) dynWrapper.classList.add('active-nav');
                
                if (shouldScroll) {
                    const itemTop = sLink.offsetTop;
                    if (itemTop < navMenu.scrollTop + 50 || itemTop > navMenu.scrollTop + navMenu.clientHeight - 50) {
                        navMenu.scrollTo({ top: itemTop - 100, behavior: 'smooth' });
                    }
                }
            }
        }

        // 滚动监听
        let isScrolling = false;
        scrollContainer.addEventListener('scroll', () => {
            isScrolling = true;
            const sections = document.querySelectorAll('.dashboard-section, .up-section');
            let currentId = "";
            const scrollPos = scrollContainer.scrollTop + 150;

            sections.forEach(section => {
                const top = getRelativeOffsetTop(section, scrollContainer);
                if (scrollPos >= top) currentId = section.id;
            });

            if (currentId) setActiveNavItem(currentId, true);
            clearTimeout(window.scrollTimer);
            window.scrollTimer = setTimeout(() => { isScrolling = false; }, 200);
        });

        // 悬停监听
        document.addEventListener('mouseover', (e) => {
            if (isScrolling) return;
            const section = e.target.closest('.dashboard-section, .up-section');
            if (section && section.id) setActiveNavItem(section.id, false);
        });

        // 平滑点击
        document.addEventListener('click', (e) => {
            const anchor = e.target.closest('a[href^="#"]');
            if (anchor) {
                const fullHref = anchor.getAttribute('href');
                let tid = fullHref.startsWith('#') ? fullHref.slice(1) : "";
                if (!tid) return;

                let targetEl = document.getElementById(tid) || 
                               (anchor.dataset.target ? document.getElementById(anchor.dataset.target) : null);
                
                if (!targetEl) {
                    try { tid = decodeURIComponent(tid); targetEl = document.getElementById(tid); } catch(err) {}
                }

                if (targetEl) {
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    setActiveNavItem(tid, false);
                }
            }
        }, true);
    }

    // 延迟初始化以确保动态内容已渲染
    setTimeout(initScrollSync, 500);
});

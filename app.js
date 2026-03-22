document.addEventListener("DOMContentLoaded", () => {
    // Theme Toggle Logic
    const themeBtn = document.getElementById("theme-toggle");
    const themeIcon = document.getElementById("theme-icon");
    const body = document.body;

    const savedTheme = localStorage.getItem("biliTheme");
    if (savedTheme === "light") {
        body.classList.add("light-mode");
        themeIcon.setAttribute("name", "sunny-outline");
    }

    if (themeBtn) {
        themeBtn.addEventListener("click", () => {
            body.classList.toggle("light-mode");
            const isLight = body.classList.contains("light-mode");
            themeIcon.setAttribute("name", isLight ? "sunny-outline" : "moon-outline");
            localStorage.setItem("biliTheme", isLight ? "light" : "dark");
        });
    }

    if (typeof REPORT_DATA === 'undefined') {
        console.error("REPORT_DATA is not defined.");
        return;
    }

    // Set Header Info
    const dateEl = document.getElementById("report-date");
    const titleEl = document.getElementById("main-title");
    
    if (REPORT_DATA.date) {
        const d = new Date(REPORT_DATA.date);
        const dateStr = `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
        dateEl.textContent = dateStr;
        
        if (REPORT_DATA.user_name) {
            titleEl.textContent = `${REPORT_DATA.user_name} 的 B站一天回顾`;
        }
    }
    
    const watchTimeEl = document.getElementById("watch-time-display");
    if (watchTimeEl) {
        watchTimeEl.textContent = REPORT_DATA.watch_time || "0分钟";
    }

    // AI Summary
    const mdContainer = document.getElementById("ai-content");
    if (REPORT_DATA.ai_summary) {
        mdContainer.innerHTML = marked.parse(REPORT_DATA.ai_summary);
    }

    // Render Function for Lists (History, Hot, Tech)
    const renderList = (dataArray, containerId, hasPlayCount) => {
        const container = document.getElementById(containerId);
        if (!dataArray || dataArray.length === 0) {
            container.innerHTML = '<span style="color:var(--text-muted);font-size:0.9rem;">暂无数据</span>';
            return;
        }

        container.innerHTML = dataArray.map(item => `
            <a href="${item.url}" target="_blank" class="media-item">
                <img src="${item.cover || 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs='}" loading="lazy" class="media-cover" alt="cover">
                <div class="media-info">
                    <div class="media-title">${item.title}</div>
                    <div class="media-meta">
                        <span><ion-icon name="person-outline"></ion-icon> ${item.author}</span>
                        ${hasPlayCount && item.play_count ? `<span><ion-icon name="play-outline"></ion-icon> ${item.play_count}</span>` : ''}
                    </div>
                </div>
            </a>
        `).join('');
    };

    renderList(REPORT_DATA.history, "history-list", false);
    renderList(REPORT_DATA.hot, "hot-list", true);
    renderList(REPORT_DATA.tech, "tech-list", true);

    // Render Game Posts
    const gameContainer = document.getElementById("game-container");
    let gameHTML = "";
    
    REPORT_DATA.games.forEach((game, index) => {
        const postCount = game.posts ? game.posts.length : 0;
        const videoCount = game.videos ? game.videos.length : 0;
        const totalUpdateCount = postCount + videoCount;
        const sectionId = `up-section-${index}`;
        let headerImageHTML = game.header ? `<img src="${game.header}" class="up-header-img" alt="header">` : `<div class="up-header-img placeholder" style="height: 140px; background: var(--glass-bg);"></div>`;


        
        let videosHTML = "";
        if (videoCount > 0) {
            videosHTML = `
                <div class="up-videos-integration">
                    <div class="integration-subtitle"><ion-icon name="videocam-outline"></ion-icon> 昨日投稿</div>
                    <div class="mini-video-list">
                        ${game.videos.map(vid => `
                            <a href="${vid.url}" target="_blank" class="mini-video-item">
                                <img src="${vid.cover}" class="mini-video-thumb">
                                <div class="mini-video-details">
                                    <div class="mini-video-text">${vid.text}</div>
                                    <div class="mini-video-meta">${vid.time}</div>
                                </div>
                            </a>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        let upHTML = `
            <div class="up-section" id="${sectionId}">
                <div class="up-header-wrapper">
                    ${headerImageHTML}
                    <div class="up-header-overlay">
                        <div style="display: flex; align-items: flex-end; gap: 15px;">
                            <img src="${game.avatar}" class="up-avatar" alt="${game.name}">
                            <h3 class="up-title">${game.name}</h3>
                        </div>
                        <div class="up-meta">
                            <span class="post-count">${totalUpdateCount} 条更新</span>
                            <button class="collapse-btn" onclick="document.getElementById('${sectionId}').classList.toggle('collapsed')">
                                <ion-icon name="chevron-up-outline"></ion-icon>
                            </button>
                        </div>
                    </div>
                </div>
                <div class="up-integrated-body">
                    ${videosHTML}
                    <div class="up-posts-integration">
                        <div class="integration-subtitle"><ion-icon name="chatbubbles-outline"></ion-icon> 最近动态</div>
                        <div class="up-posts-grid">
                            ${postCount === 0 ? `
                                <div class="game-post" style="opacity: 0.7; grid-column: 1/-1;">
                                    <div class="game-post-content" style="justify-content: center; align-items: center; min-height: 80px;">
                                        <div class="game-post-text" style="text-align: center; color: var(--text-muted);">
                                            <ion-icon name="moon-outline" style="font-size: 1.5rem; display: block; margin: 0 auto 5px;"></ion-icon>
                                            过去 24 小时没有发布新动态
                                        </div>
                                    </div>
                                </div>
                            ` : ''}`;

        game.posts.forEach(post => {
            upHTML += `
                <div class="game-post">
                    ${post.cover ? `<img src="${post.cover}" class="game-post-cover" loading="lazy" alt="cover">` : ''}
                    <div class="game-post-content">
                        <div class="game-post-text scrollable-text">${post.text || '分享了动态/视频'}</div>
                        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem;">
                            <div class="game-post-time" style="margin: 0;"><ion-icon name="time-outline"></ion-icon> ${post.time}</div>
                            <a href="${post.url}" target="_blank" style="color: var(--accent); text-decoration: none; font-weight: 600;"><ion-icon name="link-outline"></ion-icon> 查看原贴</a>
                        </div>
                    </div>
                </div>
            `;
        });
        
        upHTML += `</div></div></div></div>`;
        gameHTML += upHTML;
    });


    gameContainer.innerHTML = gameHTML;

    // Render Watch Time Trend Chart
    if (typeof TIME_TREND !== 'undefined') {
        const ctx = document.getElementById('watchTimeChart').getContext('2d');
        const labels = TIME_TREND.map(d => d.date);
        const dataPts = TIME_TREND.map(d => d.minutes);

        // Responsive styling depending on mode
        const isLight = document.body.classList.contains("light-mode");
        const gridColor = isLight ? "rgba(0,0,0,0.05)" : "rgba(255,255,255,0.05)";
        let textColor = isLight ? "#64748b" : "#94a3b8";
        
        // Define Chart
        window.watchTrendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: '观看时长 (分钟)',
                    data: dataPts,
                    borderColor: '#fb7299',
                    backgroundColor: 'rgba(251, 114, 153, 0.2)',
                    borderWidth: 3,
                    pointBackgroundColor: '#fff',
                    pointBorderColor: '#fb7299',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: 'rgba(0,0,0,0.7)',
                        titleColor: '#fff',
                        bodyColor: '#fff'
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: textColor }
                    },
                    y: {
                        grid: { color: gridColor },
                        ticks: { color: textColor, precision: 0 }
                    }
                }
            }
        });

        // Watch theme toggles to adjust chart colors
        themeBtn.addEventListener("click", () => {
             const newIsLight = document.body.classList.contains("light-mode");
             const newGridColor = newIsLight ? "rgba(0,0,0,0.05)" : "rgba(255,255,255,0.05)";
             const newTextColor = newIsLight ? "#64748b" : "#94a3b8";
             window.watchTrendChart.options.scales.x.ticks.color = newTextColor;
             window.watchTrendChart.options.scales.y.ticks.color = newTextColor;
             window.watchTrendChart.options.scales.y.grid.color = newGridColor;
             window.watchTrendChart.update();
        });
    }

});

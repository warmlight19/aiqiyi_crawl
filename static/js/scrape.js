$(document).ready(function() {
    const socket = io();
    let updateTimer = null;
    
    // 添加日志条目
    function addLogEntry(message, type = 'info') {
        const iconClass = type === 'error' ? 'fa-exclamation-circle text-danger' : 
                        type === 'success' ? 'fa-check-circle text-success' : 'fa-info-circle text-primary';
        
        const entry = $(`
            <div class="log-entry">
                <i class="fas ${iconClass} mr-2"></i>
                ${new Date().toLocaleTimeString()} - ${message}
            </div>
        `);
        
        $('#progressLog').prepend(entry);
    }
    
    // 开始爬取函数
    function startScraping() {
        const $btn = $('#startScrapingBtn');
        const $stopBtn = $('#stopScrapingBtn');
        const videoCount = parseInt($('#videoCount').val());
        const headlessMode = $('#headlessMode').prop('checked');
        const isAutoUpdate = $('#autoUpdate').prop('checked');
        const updateInterval = parseInt($('#updateInterval').val());
    
        if (isNaN(videoCount) || videoCount < 1 || videoCount > 20) {
            addLogEntry('请输入有效的视频数量（1-20）', 'error');
            return;
        }
    
        if (isAutoUpdate && (isNaN(updateInterval) || updateInterval < 30)) {
            addLogEntry('自动更新间隔不能小于30分钟', 'error');
            return;
        }
    
        $btn.prop('disabled', true);
        $stopBtn.prop('disabled', false);
        addLogEntry('开始爬取数据...');
    
        socket.emit('start_scraping', {
            videoCount: videoCount,
            headlessMode: headlessMode,
            isAutoUpdate: isAutoUpdate,
            updateInterval: updateInterval
        });
    }
    
    // 开始自动更新
    function startAutoUpdate() {
        const interval = parseInt($('#updateInterval').val()) * 60 * 1000; // 转换为毫秒
        if (updateTimer) {
            clearInterval(updateTimer);
        }
        
        // 立即执行一次爬取
        startScraping();
        
        // 设置定时器
        updateTimer = setInterval(startScraping, interval);
        addLogEntry('已启动自动更新，间隔：' + $('#updateInterval').val() + '分钟');
    }
    
    // 停止自动更新
    function stopAutoUpdate() {
        if (updateTimer) {
            clearInterval(updateTimer);
            updateTimer = null;
            addLogEntry('已停止自动更新');
        }
    }
    
    // 自动更新开关事件处理
    $('#autoUpdate').change(function() {
        const isChecked = $(this).prop('checked');
        $('#updateIntervalGroup').toggle(isChecked);
        
        if (isChecked) {
            // 启用自动更新时禁用手动按钮
            $('#startScrapingBtn').prop('disabled', true);
        } else {
            // 关闭自动更新时清除定时器并恢复手动按钮
            if (updateTimer) {
                clearInterval(updateTimer);
                updateTimer = null;
            }
            $('#startScrapingBtn').prop('disabled', false);
        }
    });
    
    // 更新间隔输入验证
    $('#updateInterval').on('input', function() {
        let value = parseInt($(this).val());
        if (value < 30) {
            $(this).val(30);
        }
    });
    
    // 开始爬取按钮点击事件
    $('#startScrapingBtn').click(function() {
        if ($('#autoUpdate').prop('checked')) {
            startAutoUpdate();
        } else {
            startScraping();
        }
    });
    
    // 停止爬取按钮
    $('#stopScrapingBtn').click(function() {
        socket.emit('stop_scraping');
        addLogEntry('正在停止爬取过程...');
        $(this).prop('disabled', true);
        stopAutoUpdate();
    });
    
    // Socket.io 事件监听
    socket.on('update_progress', function(data) {
        addLogEntry(data.message);
    });
    
    socket.on('scraping_complete', function(data) {
        $('#startScrapingBtn').html('<i class="fas fa-play mr-2"></i>开始爬取').prop('disabled', false);
        $('#stopScrapingBtn').prop('disabled', true);
        addLogEntry(data.message, data.success ? 'success' : 'error');
        
        // 更新历史记录
        loadHistory();
    });
    
    // 加载爬取历史
    function loadHistory() {
        $.get('/api/get_scrape_history')
            .done(function(data) {
                $('#historyList').empty();
                if (data.length === 0) {
                    $('#historyList').html('<div class="text-muted">暂无历史记录</div>');
                    return;
                }
                
                data.forEach(item => {
                    $('#historyList').append(`
                        <div class="mb-2">
                            <div class="font-weight-bold">${item.filename}</div>
                            <div class="text-muted small">${item.time}</div>
                        </div>
                    `);
                });
            });
    }
    
    // 初始化加载历史记录
    loadHistory();
});
// 初始化函数
function initDisplayPage() {
    console.log("初始化数据展示页面...");
    
    // 加载文件列表
    loadFileList();
    
    // 绑定事件
    $('#fileSelect').change(function() {
        const filename = $(this).val();
        loadVideoList(filename);
    });
    
    $(document).on('click', '.video-item', function(e) {
        e.preventDefault();
        $('.video-item').removeClass('active');
        $(this).addClass('active');
        
        const filename = $('#fileSelect').val();
        const videoName = $(this).data('name');
        loadVideoDetails(filename, videoName);
        
        // 隐藏推荐区域
        $('#recommendationsContainer').hide();
    });
    
    $('#searchBtn').click(handleSearch);
    
    // 绑定获取推荐视频按钮事件
    $('#getRecommendationsBtn').click(function() {
        const activeVideo = $('.video-item.active');
        if (activeVideo.length > 0) {
            const videoName = activeVideo.data('name');
            loadRecommendations(videoName);
        } else {
            alert('请先选择一个视频');
        }
    });
}

// 文件列表相关函数
function loadFileList() {
    console.log("加载文件列表...");
    showLoading('#fileSelect', '正在加载数据文件...');

    $.ajax({
        url: '/api/get_data_files',
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            console.log("获取到文件列表:", response);
            renderFileSelect(response);
        },
        error: handleFileLoadError,
        complete: function() {
            hideLoading('#fileSelect');
        }
    });
}

function renderFileSelect(files) {
    const $select = $('#fileSelect');
    $select.empty().append('<option value="">请选择...</option>');

    if (!files || files.length === 0) {
        showNoDataMessage();
        return;
    }

    files.forEach(file => {
        $select.append(`<option value="${file.full_path || file.filename}">${file.display_name}</option>`);
    });

    // 默认选择第一个文件
    if (files.length > 0) {
        const firstFile = files[0].full_path || files[0].filename;
        $select.val(firstFile).trigger('change');
    }
}

// 视频列表相关函数
function loadVideoList(filename) {
    if (!filename) {
        $('#videoList').html(`
            <div class="list-group-item text-muted text-center py-4">
                请先选择数据文件
            </div>
        `);
        $('#searchBox').hide();
        return;
    }
    
    showLoading('#videoList', '正在加载视频数据...');
    
    $.get('/api/get_video_list', { file: filename })
        .done(renderVideoList)
        .fail(handleVideoListError)
        .always(() => hideLoading('#videoList'));
}

// 修改renderVideoList函数，只显示剧名
function renderVideoList(data) {
    const $videoList = $('#videoList');
    $videoList.empty();
    
    if (data.error) {
        showVideoListError(data.error);
        return;
    }
    
    if (data.videos.length === 0) {
        $videoList.html(`
            <div class="list-group-item text-muted text-center py-4">
                没有找到视频数据
            </div>
        `);
        return;
    }
    
    // 只显示剧名，简化列表项
    data.videos.forEach((video, index) => {
        $videoList.append(`
            <a href="#" class="list-group-item list-group-item-action video-item" 
               data-index="${index}" data-name="${video.name}">
               ${video.name}
            </a>
        `);
    });
    
    $('#videoCount').text(data.videos.length);
    $('#searchBox').show();
    updateFileInfo(data);
    
    // 默认选中第一个
    $videoList.find('.video-item').first().addClass('active').trigger('click');
}

// 修改renderVideoDetails函数，完整显示详情
function renderVideoDetails(data) {
    if (data.error) {
        showErrorAlert('#videoDetailContainer', data.error);
        return;
    }
    
    // 更新海报，添加加载状态控制
    const $poster = $('#videoPoster');
    const $posterLink = $('#posterLink');
    
    // 在图片加载前显示加载状态
    $poster.addClass('loading').attr('src', '/static/default-poster.svg');
    
    if (data.poster_url) {
        const posterUrl = '/proxy_image?url=' + encodeURIComponent(data.poster_url);
        // 预加载图片
        const img = new Image();
        img.onload = function() {
            $poster.removeClass('loading').attr('src', posterUrl);
            $posterLink.attr('href', data.link || '#');
        };
        img.onerror = function() {
            $poster.removeClass('loading').attr('src', '/static/default-poster.svg');
            $posterLink.attr('href', '#');
        };
        img.src = posterUrl;
    } else {
        $poster.removeClass('loading').attr('src', '/static/default-poster.svg');
        $posterLink.attr('href', '#');
    }
    
    // 更新基本信息
    $('#videoTitle').text(data.name);
    $('#videoRating').text(data.rating || '无评分');
    $('#ratingCount').text(`(${data.rating_count || 0}人评价)`);
    $('#watchLink').attr('href', data.link || '#');
    $('#videoDescription').text(data.description || '暂无描述');
    
    // 更新演职人员
    const $castContainer = $('#videoCast');
    $castContainer.empty();
    if (data.cast && data.cast !== '未知' && data.cast.trim() !== '') {
        const actors = data.cast.split(/[,|]/).filter(a => a.trim());
        if (actors.length > 0) {
            actors.forEach(actor => {
                $castContainer.append(`<span class="badge badge-secondary m-1">${actor.trim()}</span>`);
            });
        } else {
            $castContainer.append('<span class="text-muted">未知</span>');
        }
    } else {
        $castContainer.append('<span class="text-muted">未知</span>');
    }
    
    // 更新评论
    if (data.comments && Array.isArray(data.comments) && data.comments.length > 0) {
        console.log('渲染评论数据，数量:', data.comments.length);
        renderComments(data.comments);
    } else {
        console.log('无评论数据');
        $('#videoComments').html(`
            <div class="alert alert-warning m-3">
                <i class="fas fa-comment-slash mr-2"></i>
                暂无评论数据
            </div>
        `);
        $('#commentCount').text('0条');
    }
}

// 加载推荐视频
function loadRecommendations(videoName) {
    if (!videoName) {
        console.error('视频名称不能为空');
        return;
    }
    
    console.log('加载推荐视频:', videoName);
    
    // 显示加载状态
    showLoading('#recommendationsContainer', '正在加载推荐内容...');
    $('#recommendationsContainer').show();
    
    $.get('/api/get_recommendations', { video_name: videoName })
        .done(function(data) {
            if (data.error) {
                $('#recommendationsList').html(`
                    <div class="col-12 text-center py-4 text-danger">
                        <i class="fas fa-exclamation-circle mr-2"></i>${data.error}
                    </div>
                `);
                $('#recommendCount').text('0条');
                return;
            }
            renderRecommendations(data.recommendations);
        })
        .fail(function(jqXHR, textStatus, errorThrown) {
            console.error('加载推荐失败:', errorThrown);
            let errorMessage = '加载推荐失败';
            if (jqXHR.responseJSON && jqXHR.responseJSON.error) {
                errorMessage += `: ${jqXHR.responseJSON.error}`;
            } else if (errorThrown) {
                errorMessage += `: ${errorThrown}`;
            }
            
            $('#recommendationsList').html(`
                <div class="col-12 text-center py-4 text-danger">
                    <i class="fas fa-exclamation-circle mr-2"></i>${errorMessage}
                    <div class="small text-muted mt-2">请稍后重试</div>
                </div>
            `);
            $('#recommendCount').text('0条');
        })
        .always(function() {
            hideLoading('#recommendationsContainer');
        });
}

// 渲染推荐视频列表
function renderRecommendations(recommendations) {
    const $container = $('#recommendationsList');
    const $recommendCount = $('#recommendCount');
    $container.empty();
    
    if (!recommendations || recommendations.length === 0) {
        $container.html(`
            <div class="col-12 text-center py-4">
                <i class="fas fa-info-circle mr-2"></i>暂无推荐内容
            </div>
        `);
        $recommendCount.text('0条');
    } else {
        recommendations.forEach(item => {
            // 使用poster_url字段作为海报URL
            const posterUrl = item.poster_url ? '/proxy_image?url=' + encodeURIComponent(item.poster_url) : '/static/default-poster.svg';
            
            // 使用cast字段显示演员信息
            const castList = item.cast ? item.cast.split(/[,|]/).filter(a => a.trim()) : [];
            
            // 解析comments字段
            let comments = [];
            try {
                if (typeof item.comments === 'string') {
                    // 替换单引号为双引号，以确保JSON解析正确
                    const commentsStr = item.comments.replace(/'/g, '"');
                    comments = JSON.parse(commentsStr);
                } else if (Array.isArray(item.comments)) {
                    comments = item.comments;
                }
                
                // 按点赞数排序评论
                comments.sort((a, b) => parseInt(b.like_count || 0) - parseInt(a.like_count || 0));
            } catch (e) {
                console.error('解析评论数据失败:', e);
                console.error('原始评论数据:', item.comments);
            }
            
            $container.append(`
                <div class="col-12 mb-4">
                    <div class="card h-100">
                        <div class="row no-gutters">
                            <div class="col-md-3">
                                <img src="${posterUrl}" 
                                     class="card-img h-100" alt="${item.name}"
                                     style="object-fit: cover;"
                                     onerror="this.src='/static/default-poster.svg'">
                            </div>
                            <div class="col-md-9">
                                <div class="card-body">
                                    <div class="d-flex justify-content-between align-items-start mb-2">
                                        <h5 class="card-title mb-0">${item.name}</h5>
                                        <div>
                                            <span class="badge badge-primary mr-2">${item.rating || '暂无评分'}</span>
                                            <span class="text-muted small">${item.rating_count || 0}人评价</span>
                                        </div>
                                    </div>
                                    <p class="card-text">${item.description || '暂无描述'}</p>
                                    <div class="mb-3">
                                        <h6 class="mb-2">演职人员：</h6>
                                        <div class="cast-container">
                                            ${castList.length > 0 ? 
                                                castList.map(actor => `<span class="badge badge-secondary mr-1">${actor.trim()}</span>`).join('') : 
                                                '<span class="text-muted">未知</span>'
                                            }
                                        </div>
                                    </div>
                                    <div class="mb-3">
                                        <h6 class="mb-2">热门评论：</h6>
                                        <div class="comments-preview" style="max-height: 200px; overflow-y: auto;">
                                            ${comments && comments.length > 0 ? 
                                                comments.slice(0, 10).map(comment => `
                                                    <div class="media mb-2 pb-2 border-bottom">
                                                        <img src="${comment.avatar_url ? '/proxy_image?url=' + encodeURIComponent(comment.avatar_url) : '/static/default-avatar.svg'}" 
                                                             class="mr-2 rounded-circle" 
                                                             style="width: 32px; height: 32px;"
                                                             alt="${comment.nickname || '匿名用户'}"
                                                             onerror="this.src='/static/default-avatar.svg'">
                                                        <div class="media-body">
                                                            <div class="d-flex justify-content-between">
                                                                <div>
                                                                    <h6 class="mt-0 mb-1 small">${comment.nickname || '匿名用户'}</h6>
                                                                    <small class="text-muted">ID: ${comment.user_id || '未知'}</small>
                                                                </div>
                                                                <small class="text-muted">${comment.comment_time || ''}</small>
                                                            </div>
                                                            <p class="mb-1 small">${comment.comment_content || ''}</p>
                                                            <div class="d-flex align-items-center">
                                                                <small class="text-muted">
                                                                    <i class="fas fa-thumbs-up mr-1"></i>${comment.like_count || 0} 赞
                                                                </small>
                                                            </div>
                                                        </div>
                                                    </div>
                                                `).join('') : 
                                                '<div class="text-muted small">暂无评论</div>'
                                            }
                                        </div>
                                    </div>
                                    <div class="mt-3">
                                        <a href="${item.link}" target="_blank" class="btn btn-primary">
                                            <i class="fas fa-play mr-1"></i>立即观看
                                        </a>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `);
        });
        $recommendCount.text(`${recommendations.length}条`);
    }
    
    $('#recommendationsContainer').show();
}

// 修改渲染评论函数，确保显示完整的评论信息
function renderComments(comments) {
    console.log('开始渲染评论列表，评论数量:', comments ? comments.length : 0);
    const $commentsContainer = $('#videoComments');
    $commentsContainer.empty();
    
    if (!comments || comments.length === 0) {
        $commentsContainer.html(`
            <div class="alert alert-warning m-3">
                <i class="fas fa-comment-slash mr-2"></i>
                暂无评论数据
            </div>
        `);
        $('#commentCount').text('0条');
        return;
    }
    
    // 按点赞数排序评论
    comments.sort((a, b) => (b.likes || 0) - (a.likes || 0));
    
    // 更新评论计数
    $('#commentCount').text(`${comments.length}条`);
    
    comments.forEach((comment, index) => {
        console.log(`处理第${index + 1}条评论:`, {
            用户名: comment.user_name,
            用户ID: comment.user_id,
            头像URL: comment.avatar_url,
            评论内容: comment.content,
            点赞数: comment.likes,
            评论时间: comment.time
        });
        
        const avatarUrl = comment.avatar_url ? '/proxy_image?url=' + encodeURIComponent(comment.avatar_url) : '/static/default-avatar.svg';
        console.log(`使用的头像URL: ${avatarUrl}`);
        
        const commentHtml = `
            <div class="media p-3 border-bottom">
                <img src="${avatarUrl}" class="mr-3 rounded-circle user-avatar" 
                     alt="${comment.user_name || '匿名用户'}" 
                     onerror="this.src='/static/default-avatar.svg'">
                <div class="media-body">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mt-0 mb-1 user-name">${comment.user_name || '匿名用户'}</h6>
                            <small class="text-muted">ID: ${comment.user_id || '未知'}</small>
                        </div>
                        <small class="text-muted comment-time">${comment.time || ''}</small>
                    </div>
                    <p class="mb-1 comment-content">${comment.content}</p>
                    <small class="text-muted like-count">
                        <i class="fas fa-thumbs-up mr-1"></i>${comment.likes || 0} 赞
                    </small>
                </div>
            </div>
        `;
        $commentsContainer.append(commentHtml);
    });
}

function createVideoItem(video, index) {
    return `
        <a href="#" class="list-group-item list-group-item-action video-item" 
           data-index="${index}" data-name="${video.name}">
            <div class="d-flex justify-content-between align-items-center">
                <span class="text-truncate">${video.name}</span>
                ${video.rating ? `
                <span class="badge badge-primary rating-badge">
                    ${parseFloat(video.rating).toFixed(1)}
                </span>
                ` : '<span class="text-muted small">无评分</span>'}
            </div>
        </a>
    `;
}

// 新增评分格式化函数
function formatRating(rating) {
    if (!rating || rating === '无评分') return '无评分';
    
    // 处理包含换行符的情况
    rating = rating.toString().replace(/\n/g, ' ').trim();
    
    // 提取数字部分
    const numMatch = rating.match(/(\d+\.?\d*)/);
    if (numMatch) {
        return parseFloat(numMatch[1]).toFixed(1);
    }
    
    return '无评分';
}

// 视频详情相关函数
function loadVideoDetails(filename, videoName) {
    showLoading('#videoDetailContainer', '正在加载详情...');
    
    $.get('/api/get_video_details', { file: filename, name: videoName })
        .done(function(data) {
            console.log('获取到视频详情:', data);
            console.log('海报URL:', data.poster_url);
            renderVideoDetails(data);
        })
        .fail(handleVideoDetailsError)
        .always(() => hideLoading('#videoDetailContainer'));
}

function renderVideoDetails(data) {
    if (data.error) {
        showErrorAlert('.main-content', data.error);
        return;
    }
    
    console.log('开始渲染视频详情，海报URL:', data.poster_url);
    // 更新海报和链接
    const posterUrl = data.poster_url ? '/proxy_image?url=' + encodeURIComponent(data.poster_url) : '/static/default-poster.svg';
    console.log('处理后的海报URL:', posterUrl);
    
    const $poster = $('#videoPoster');
    const $posterLink = $('#posterLink');
    
    // 预加载图片
    const img = new Image();
    img.onload = function() {
        console.log('海报图片加载成功');
        $poster.attr('src', posterUrl);
        $posterLink.attr('href', data.link || '#');
    };
    img.onerror = function() {
        console.error('海报图片加载失败，使用默认图片');
        $poster.attr('src', '/static/default-poster.svg');
        $posterLink.attr('href', '#');
    };
    img.src = posterUrl;
    
    // 更新基本信息
    $('#videoTitle').text(data.name);
    $('#videoRating').text(data.rating || '无评分');
    $('#ratingCount').text(`(${data.rating_count || 0}人评价)`);
    $('#watchLink').attr('href', data.link || '#');
    $('#videoDescription').text(data.description || '暂无描述');
    
    // 更新演职人员
    const $castContainer = $('#videoCast');
    $castContainer.empty();
    if (data.cast && data.cast !== '未知' && data.cast.trim() !== '') {
        const actors = data.cast.split(/[,|]/).filter(a => a.trim());
        if (actors.length > 0) {
            actors.forEach(actor => {
                $castContainer.append(`<span class="badge badge-secondary m-1">${actor.trim()}</span>`);
            });
        } else {
            $castContainer.append('<span class="text-muted">未知</span>');
        }
    } else {
        $castContainer.append('<span class="text-muted">未知</span>');
    }
    
    // 更新评论
    if (data.comments && Array.isArray(data.comments)) {
        console.log('评论数据:', data.comments);
        renderComments(data.comments);
    } else {
        console.warn('没有评论数据或格式不正确:', data.comments);
        renderComments([]);
    }
}

function createVideoPosterCard(data) {
    // 处理评分显示
    let ratingDisplay = '无评分';
    if (data.rating && data.rating !== '无') {
        ratingDisplay = parseFloat(data.rating).toFixed(1);
    }
    
    return `
        <div class="card mb-4 sticky-top" style="top: 20px;">
            <img src="${data.poster_url ? '/proxy_image?url=' + encodeURIComponent(data.poster_url) : '/static/default-poster.svg'}" 
                 class="card-img-top video-poster" alt="剧集海报" style="height: 450px; object-fit: cover;">
            <div class="card-body">
                <h3 class="card-title">${data.name}</h3>
                <div class="d-flex align-items-center mb-3">
                    <span class="badge badge-primary rating-badge mr-2">
                        ${ratingDisplay}
                    </span>
                    <small class="text-muted">(${data.rating_count || 0}人评价)</small>
                </div>
                <a href="${data.link || '#'}" target="_blank" class="btn btn-sm btn-outline-primary btn-block">
                    <i class="fas fa-play mr-1"></i>观看链接
                </a>
            </div>
        </div>
    `;
}

function createCastCard(cast) {
    return `
        <div class="card mb-4">
            <div class="card-header">
                <h5><i class="fas fa-users mr-2"></i>演职人员</h5>
            </div>
            <div class="card-body">
                <div class="cast-container">
                    ${formatCast(cast)}
                </div>
            </div>
        </div>
    `;
}

function createDescriptionCard(description) {
    return `
        <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h4><i class="fas fa-info-circle mr-2"></i>剧情简介</h4>
            </div>
            <div class="card-body">
                <p class="card-text description-content" style="white-space: pre-line;">${description || '暂无描述'}</p>
            </div>
        </div>
    `;
}

function createCommentsSection(comments) {
    if (!comments || comments.length === 0) {
        return `
            <div class="alert alert-warning">
                <i class="fas fa-comment-slash mr-2"></i>
                暂无评论数据
            </div>
        `;
    }
    
    // 按点赞数排序
    comments.sort((a, b) => (b.likes || 0) - (a.likes || 0));
    
    const commentsHtml = comments.map(comment => `
        <div class="media comment-item mb-3 p-2 border-bottom">
            <img src="${comment.avatar ? '/proxy_image?url=' + encodeURIComponent(comment.avatar) : 'https://via.placeholder.com/50?text=User'}" 
                 class="mr-3 rounded-circle user-avatar" width="50" height="50" alt="用户头像">
            <div class="media-body">
                <div class="d-flex justify-content-between">
                    <h6 class="mt-0 user-name">${comment.user || '匿名用户'}</h6>
                    <small class="text-muted comment-time">${formatTime(comment.time)}</small>
                </div>
                <div class="comment-content mb-2">${comment.content || ''}</div>
                <div class="d-flex justify-content-between align-items-center">
                    <button class="btn btn-sm btn-outline-danger like-btn">
                        <i class="fas fa-heart mr-1"></i>
                        <span class="like-count">${comment.likes || 0}</span>
                    </button>
                </div>
            </div>
        </div>
    `).join('');
    
    return `
        <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h4><i class="fas fa-comments mr-2"></i>热门评论</h4>
                <span class="badge badge-pill badge-info">${comments.length}条</span>
            </div>
            <div class="card-body">
                <div class="comment-list">
                    ${commentsHtml}
                </div>
            </div>
        </div>
    `;
}

// 工具函数
function formatCast(cast) {
    if (!cast || cast === '未知' || cast === '无演员表') return '未知';
    
    // 处理不同的演员表格式
    let actors = [];
    if (cast.includes('|')) {
        actors = cast.split('|').filter(a => a.trim());
    } else if (cast.includes(',')) {
        actors = cast.split(',').filter(a => a.trim());
    } else {
        actors = [cast.trim()];
    }
    
    if (actors.length === 0) return '未知';
    
    return actors.map(actor => 
        `<span class="badge badge-secondary mr-1 mb-1">${actor.trim()}</span>`
    ).join('');
}

function formatTime(timeStr) {
    if (!timeStr) return '';
    try {
        return new Date(timeStr).toLocaleString();
    } catch {
        return timeStr;
    }
}

function showLoading(selector, text) {
    $(selector).prop('disabled', true);
    $(selector).after(`
        <div class="loading-container">
            <div class="spinner-border spinner-border-sm text-primary mr-2"></div>
            <span class="loading-text small">${text}</span>
        </div>
    `);
}

function hideLoading(selector) {
    $(selector).prop('disabled', false);
    $(selector).next('.loading-container').remove();
}

function showNoDataMessage() {
    $('#fileSelect').append('<option value="" disabled>没有可用的数据文件</option>');
    $('#videoList').html(`
        <div class="list-group-item text-center py-4">
            <i class="fas fa-exclamation-circle mr-2"></i>
            没有找到符合格式的数据文件
            <div class="small text-muted mt-2">
                请检查 data/hotdata 目录下是否有 iqiyi_YYYYMMDD_HHMMSS.csv 文件
            </div>
        </div>
    `);
}

function handleFileLoadError(xhr) {
    let errorMsg = '加载文件列表失败';
    if (xhr.responseJSON && xhr.responseJSON.error) {
        errorMsg += `: ${xhr.responseJSON.error}`;
    }
    
    $('#fileSelect').html('<option value="" disabled>' + errorMsg + '</option>');
    $('#videoList').html(`
        <div class="list-group-item text-center py-4 text-danger">
            <i class="fas fa-exclamation-triangle mr-2"></i>
            ${errorMsg}
        </div>
    `);
}

function handleVideoListError(xhr) {
    let errorMsg = '加载视频列表失败';
    if (xhr.responseJSON && xhr.responseJSON.error) {
        errorMsg += `: ${xhr.responseJSON.error}`;
    }
    
    $('#videoList').html(`
        <div class="list-group-item text-danger">
            <i class="fas fa-exclamation-circle mr-2"></i>
            ${errorMsg}
        </div>
    `);
}

function handleVideoDetailsError(xhr) {
    let errorMsg = '加载详情失败';
    if (xhr.responseJSON && xhr.responseJSON.error) {
        errorMsg += `: ${xhr.responseJSON.error}`;
    }
    
    $('#videoDetailContainer').html(`
        <div class="alert alert-danger">
            <i class="fas fa-exclamation-circle mr-2"></i>
            ${errorMsg}
        </div>
    `);
}

function showErrorAlert(selector, message) {
    $(selector).html(`
        <div class="alert alert-danger">
            <i class="fas fa-exclamation-circle mr-2"></i>
            ${message}
        </div>
    `);
}

function updateFileInfo(data) {
    $('#fileInfo').html(`
        <i class="fas fa-database mr-1"></i> ${data.count} 条记录
        <span class="float-right">
            <i class="fas fa-calendar-alt mr-1"></i> ${data.crawl_time}
        </span>
    `);
}

function handleSearch() {
    const keyword = $('#searchInput').val().trim();
    if (!keyword) return;
    
    const $items = $('.video-item');
    let found = false;
    
    $items.each(function() {
        const itemText = $(this).text().toLowerCase();
        if (itemText.includes(keyword.toLowerCase())) {
            $(this).show();
            if (!found) {
                $(this).click();
                found = true;
            }
        } else {
            $(this).hide();
        }
    });
    
    if (!found) {
        $('#videoDetailContainer').html(`
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-circle mr-2"></i>
                没有找到匹配的剧集
            </div>
        `);
    }
}







// // 获取推荐视频按钮点击事件
// $('#getRecommendationsBtn').click(function() {
//     // 获取当前显示的视频信息
//     const videoUrl = $('#posterLink').attr('href');
//     const videoTitle = $('#videoTitle').text();
    
//     if (!videoUrl) {
//         alert('当前没有可用的视频信息');
//         return;
//     }

//     // 显示加载状态
//     const btn = $(this);
//     btn.html('<i class="fas fa-spinner fa-spin mr-2"></i>获取中...');
//     btn.prop('disabled', true);

//     // 调用API获取推荐视频
//     $.ajax({
//         url: '/api/recommendations',
//         type: 'POST',
//         contentType: 'application/json',
//         data: JSON.stringify({
//             video_url: videoUrl,
//             video_title: videoTitle
//         }),
//         success: function(response) {
//             if (response.success) {
//                 // 显示推荐结果
//                 displayRecommendations(response.recommendations, videoTitle);
//             } else {
//                 alert('获取推荐失败: ' + (response.error || '未知错误'));
//             }
//         },
//         error: function(xhr) {
//             alert('请求失败: ' + xhr.statusText);
//         },
//         complete: function() {
//             btn.html('<i class="fas fa-magic mr-2"></i>获取推荐视频');
//             btn.prop('disabled', false);
//         }
//     });
// });

// // 获取当前显示的视频信息
// function getCurrentVideoInfo() {
//     return {
//         title: $('#videoTitle').text().trim(),
//         url: $('#posterLink').attr('href'),
//         poster: $('#videoPoster').attr('src')
//     };
// }

// // 显示推荐视频的函数
// function displayRecommendations(recommendations) {
//     // 创建推荐结果容器
//     const container = $('<div class="recommendations-grid"></div>');
    
//     if (!recommendations || recommendations.length === 0) {
//         container.html('<div class="text-center py-4 text-muted">暂无推荐结果</div>');
//     } else {
//         recommendations.forEach(item => {
//             container.append(`
//             <div class="recommendation-item">
//                 <a href="${item.url || '#'}" target="_blank">
//                     <img src="${item.poster || '/static/default-poster.svg'}" 
//                          class="recommendation-poster"
//                          onerror="this.src='/static/default-poster.svg'">
//                     <div class="recommendation-info">
//                         <h6>${item.title || '未知标题'}</h6>
//                         <span class="badge badge-primary">${item.rating || '无评分'}</span>
//                     </div>
//                 </a>
//             </div>`);
//         });
//     }

//     // 使用Bootstrap模态框显示结果
//     const modalHtml = `
//     <div class="modal fade" id="recommendationsModal" tabindex="-1">
//         <div class="modal-dialog modal-lg">
//             <div class="modal-content">
//                 <div class="modal-header">
//                     <h5 class="modal-title">基于"${$('#videoTitle').text().trim()}"的推荐</h5>
//                     <button type="button" class="close" data-dismiss="modal">
//                         <span>&times;</span>
//                     </button>
//                 </div>
//                 <div class="modal-body">
//                     ${container.prop('outerHTML')}
//                 </div>
//                 <div class="modal-footer">
//                     <button type="button" class="btn btn-secondary" data-dismiss="modal">关闭</button>
//                 </div>
//             </div>
//         </div>
//     </div>`;
    
//     $('body').append(modalHtml);
//     $('#recommendationsModal').modal('show');
    
//     // 模态框关闭时清理
//     $('#recommendationsModal').on('hidden.bs.modal', function() {
//         $(this).remove();
//     });
// }







// 页面加载完成后初始化
$(document).ready(initDisplayPage);
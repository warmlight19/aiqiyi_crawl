from flask import jsonify
from flask_socketio import emit
import scraper
import threading
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# 全局变量用于控制爬虫状态
scraping_thread = None
stop_scraping = False
auto_update_timer = None
last_update_time = None

def emit_progress(message):
    """发送进度消息到前端"""
    emit('update_progress', {'message': message})

def scraping_task(socket, video_count=3, headless_mode=False, is_auto_update=False):
    """爬虫任务"""
    global stop_scraping
    try:
        # 设置浏览器驱动
        socket.emit('update_progress', {'message': '正在启动浏览器...'})        
        driver = scraper.setup_driver(headless=headless_mode)
        
        try:
            # 访问爱奇艺首页并登录
            socket.emit('update_progress', {'message': '正在访问爱奇艺首页...'})            
            driver.get("https://www.iqiyi.com/")
            # 等待页面完全加载
            try:
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                from selenium.webdriver.common.by import By
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except Exception as e:
                socket.emit('update_progress', {'message': f'等待页面加载超时: {str(e)}'})
            time.sleep(5)  # 额外等待确保页面完全加载
            
            socket.emit('update_progress', {'message': '正在尝试登录...'})            
            scraper.outo_login(driver)
            time.sleep(5)  # 增加等待时间确保登录完成
            
            
            if stop_scraping:
                raise Exception('用户停止了爬取')
            
            # 点击"最热"标签
            socket.emit('update_progress', {'message': '正在切换到最热标签...'})
            scraper.click_hottest_tab(driver)
            time.sleep(5)  # 增加等待时间确保标签切换后内容加载完成
            
            if stop_scraping:
                raise Exception('用户停止了爬取')
            
            # 获取视频列表
            socket.emit('update_progress', {'message': '正在获取视频列表...'})
            videos = scraper.get_video_list(driver, video_count=video_count)
            if not videos:
                raise Exception('未获取到视频列表')
            
            socket.emit('update_progress', {'message': f'共获取到 {len(videos)} 个视频'})
            
            # 使用线程池并行获取视频详细信息和评论
            all_details = []
            max_workers = min(10, len(videos))  # 限制最大线程数
            
            # Initialize a lock for thread-safe operations
            lock = Lock()

            def process_video(video_data):
                if stop_scraping:
                    return None
                
                video_name = video_data['name']
                socket.emit('update_progress', {'message': f'正在处理视频: {video_name}'})
                
                # Use lock to ensure thread-safe operations
                with lock:
                    # 获取视频基本信息
                    socket.emit('update_progress', {'message': f'正在获取视频 {video_name} 的基本信息...'})
                    video_info = scraper.get_video_info(driver, video_name, video_data['link'], video_data['poster_url'])
                    if not video_info:
                        socket.emit('update_progress', {'message': f'无法获取视频 {video_name} 的基本信息，跳过'})
                        return None
                    
                    # 获取视频评论
                    socket.emit('update_progress', {'message': f'正在获取视频 {video_name} 的评论...'})
                    comments = scraper.get_video_comments(driver, video_name, video_data['link'])
                    video_info['comments'] = comments
                    socket.emit('update_progress', {'message': f'获取到 {len(comments)} 条评论'})
                    
                return video_info
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_video = {executor.submit(process_video, video): video for video in videos}
                
                # 处理完成的任务
                for future in as_completed(future_to_video):
                    if stop_scraping:
                        break
                    
                    video = future_to_video[future]
                    try:
                        video_info = future.result()
                        if video_info:
                            all_details.append(video_info)
                    except Exception as e:
                        socket.emit('update_progress', {'message': f'处理视频 {video["name"]} 时出错: {str(e)}'})
                        continue
            
            # 保存结果
            if all_details:
                socket.emit('update_progress', {'message': '正在保存数据...'})
                scraper.save_to_csv(all_details)
                socket.emit('scraping_complete', {'message': '爬取完成！数据已保存', 'success': True})
            else:
                socket.emit('scraping_complete', {'message': '未获取到有效数据', 'success': False})
                
        except Exception as e:
            socket.emit('scraping_complete', {'message': f'爬取过程出错: {str(e)}', 'success': False})
        finally:
            driver.quit()
            
    except Exception as e:
        socket.emit('scraping_complete', {'message': f'启动浏览器失败: {str(e)}', 'success': False})

def init_scraping_routes(socketio):
    """初始化Socket.IO事件处理"""
    @socketio.on('start_scraping')
    def handle_start_scraping(data):
        global scraping_thread, stop_scraping, auto_update_timer, last_update_time
        
        if scraping_thread and scraping_thread.is_alive():
            emit('update_progress', {'message': '爬取任务已在进行中'})
            return
        
        try:
            video_count = int(data.get('videoCount'))
            if not isinstance(video_count, int) or video_count < 1 or video_count > 20:
                emit('update_progress', {'message': '无效的视频数量参数'})
                return
            
            headless_mode = bool(data.get('headlessMode', False))
            is_auto_update = bool(data.get('isAutoUpdate', False))
            update_interval = int(data.get('updateInterval', 30)) if is_auto_update else None
            
            # 检查更新间隔是否合法
            if is_auto_update and update_interval < 30:
                emit('update_progress', {'message': '更新间隔不能小于30分钟'})
                return
            
            stop_scraping = False
            last_update_time = datetime.now()
            
            # 启动爬虫线程
            scraping_thread = threading.Thread(
                target=scraping_task,
                args=(socketio, video_count, headless_mode, is_auto_update)
            )
            scraping_thread.start()
            
            # 如果启用了自动更新，设置定时器
            if is_auto_update and update_interval:
                if auto_update_timer:
                    auto_update_timer.cancel()
                
                def schedule_next_update():
                    global scraping_thread, last_update_time
                    if not stop_scraping:
                        current_time = datetime.now()
                        if not last_update_time or \
                           (current_time - last_update_time) >= timedelta(minutes=update_interval):
                            if not scraping_thread or not scraping_thread.is_alive():
                                last_update_time = current_time
                                scraping_thread = threading.Thread(
                                    target=scraping_task,
                                    args=(socketio, video_count, headless_mode, True)
                                )
                                scraping_thread.start()
                
                auto_update_timer = threading.Timer(update_interval * 60, schedule_next_update)
                auto_update_timer.start()
        except ValueError:
            emit('update_progress', {'message': '无效的视频数量参数'})
            return
    
    @socketio.on('stop_scraping')
    def handle_stop_scraping():
        global stop_scraping
        stop_scraping = True
        emit('update_progress', {'message': '正在停止爬取...'})
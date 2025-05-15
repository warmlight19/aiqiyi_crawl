import os
import re
import time
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import logging
import requests

# 创建线程锁
file_lock = threading.Lock()
print_lock = threading.Lock()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
from datetime import datetime

def setup_driver(headless=False):
    """
    配置并启动 Chrome 浏览器驱动
    :return: 浏览器驱动对象
    """
    chrome_options = Options()
    chrome_options.add_argument("--ignore-certificate-errors")
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--log-level=3")  # 3 表示只显示 FATAL 级别的日志
    # chrome_options.add_argument('--disable-gpu')  # 禁用GPU硬件加速
    # chrome_options.add_argument('--disable-software-rasterizer')  # 禁用软件渲染后备
    # chrome_options.add_argument('--use-angle=swiftshader')  # 强制使用 SwiftShader 软件渲染
    # chrome_options.add_argument('--disable-features=Vulkan')  

    chrome_driver_path = 'D:\\python3.10.3\\chromedriver.exe'
    service = Service(chrome_driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.maximize_window()
    return driver

def outo_login(driver):
    """
    添加Cookie到当前会话，实现登录
    """
    with open('iqiyi_cookies.json', 'r') as f:
        cookies = json.load(f)

    for cookie in cookies:
        driver.add_cookie(cookie)
        
    driver.refresh()

def parse_csv(file_path):
    try:
        # 读取时指定错误处理回调
        def parse_error_handler(error):
            logging.error(f"解析错误发生在行 {error.row}: {str(error)}")
            logging.error(f"错误行内容：{error.line}")
            return

        df = pd.read_csv(file_path, on_bad_lines=parse_error_handler)
        
        # 尝试反序列化评论字段
        if 'comments' in df.columns:
            def safe_json_loads(x):
                if pd.isna(x):
                    return []
                try:
                    # 预处理非法字符（包含更多特殊字符处理）
                    x = re.sub(r'[\x00-\x1F\x7F]', '', x)
                    x = x.replace('\\', '/')
                    decoder = json.JSONDecoder(strict=False)
                    return decoder.decode(x)
                except json.JSONDecodeError as e:
                    logging.error(f"评论数据解析失败，原始内容长度：{len(x)}，截取片段：{x[max(0,e.pos-50):e.pos+50]}")
                    return []
                except Exception as e:
                    logging.error(f"未知解析错误：{str(e)}")
                    return []

            df['comments'] = df['comments'].apply(safe_json_loads)
        
        return df
    except pd.errors.EmptyDataError:
        logging.warning(f'文件 {file_path} 为空，使用默认值填充')
        return pd.DataFrame()
    except pd.errors.ParserError as e:
        logging.error(f'解析文件 {file_path} 时出错: {str(e)}')
        return pd.DataFrame()
    except Exception as e:
        logging.error(f'处理文件 {file_path} 时发生未知错误: {str(e)}', exc_info=True)
        return pd.DataFrame()


def click_hottest_tab(driver):
    """
    点击爱奇艺首页的"最热"标签
    :param driver: 浏览器驱动对象
    """
    try:
        # 等待最热标签出现
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//div[@data-role="button" and contains(.//span, "最热")]'))
        )
        hottest_tab = driver.find_element(By.XPATH, '//div[@data-role="button" and contains(.//span, "最热")]')
        hottest_tab.click()
        # 等待点击后内容加载
        time.sleep(3)
    except Exception as e:
        print(f"无法找到或点击最热标签：{e}")
        time.sleep(2)
    time.sleep(1)

def get_video_list(driver, video_count=10): ######################################
    """
    获取"最热"标签下的视频列表
    :param driver: 浏览器驱动对象
    :param video_count: 要爬取的视频数量
    :return: 视频列表，包含视频名称和链接
    """
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')

    # 查找视频卡片
    video_cards = soup.find_all('div', class_='flex-video-list_flexTilesItem__bhNS9')
    videos = []

    for card in video_cards[:video_count]:
        # 提取视频名称
        video_name_tag = card.find('p', class_='undefined flex-video-list_title__pTUUg')
        video_name = video_name_tag.get_text(strip=True) if video_name_tag else None
        
        # 提取视频链接
        parent_link = card.find('a')
        video_link = parent_link['href'] if parent_link and parent_link.get('href') else None
        
        # 提取封面图片链接
        poster_img = card.find('img', class_='flex-video-list_poster__cNMg+')
        poster_url = poster_img['src'] if poster_img and poster_img.get('src') else "static/default-poster.svg"
        if not poster_url:
            print(f"未找到 {video_name} 的封面图片链接")
        
        # 将视频信息保存到列表
        if video_name and video_link and poster_url:
            videos.append({
                "name": video_name,
                "link": video_link,
                "poster_url": poster_url  # 新增封面图片链接字段
            })

    return videos

def get_video_info(driver, video_name, video_link, poster_url, is_recommendation=False):
    """
    获取单个视频的基本信息，包括评分次数、简介、演员表
    :param driver: 浏览器驱动对象
    :param video_name: 视频名称
    :param video_link: 视频链接
    :return: 视频基本信息
    """
    driver.get(video_link)
    # 等待页面完全加载
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except Exception as e:
        print(f"等待页面加载超时: {e}")
    time.sleep(3)  # 额外等待确保动态内容加载完成

    if not is_recommendation:
        # 如果不是推荐视频，先获取推荐视频信息
        recommendations = get_recommended_videos(driver)
        if recommendations:
            save_recommendations_to_csv(video_name, recommendations)
    
    driver.get(video_link)
    # 等待页面完全加载
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except Exception as e:
        print(f"等待页面加载超时: {e}")
    time.sleep(3)  # 额外等待确保动态内容加载完成

    try:
        detail_button = driver.find_element(By.XPATH, '//div[@class="meta_arrowBtn__gw1b5 meta_detailBtn__2XYRK"]')
        detail_button.click()
    except Exception as e:
        print(f"无法点击详情按钮：{e}")
        return None
    time.sleep(1)

    detail_page_source = driver.page_source
    detail_soup = BeautifulSoup(detail_page_source, 'html.parser')

    # 设置评分和评分人数的默认值
    rating = detail_soup.find('div', class_='score_scoreLabel__fYRiV')
    rating = rating.get_text(strip=True) if rating and rating.get_text(strip=True) else "暂无推荐分\n敬请期待"
    
    rating_count = detail_soup.find('div', class_='score_scoreCount__aNzvS')
    rating_count = rating_count.get_text(strip=True) if rating_count else "暂无评价"
    
    # 设置简介的默认值
    description = detail_soup.find('div', class_='metaDetail_infoValue__NNS+T')
    description = description.get_text(strip=True) if description else "暂无简介"
    
    # 设置演员表的默认值
    cast_list = detail_soup.find_all('div', class_='star-list_name__VSd6I')
    cast = ", ".join([cast.get_text(strip=True) for cast in cast_list]) if cast_list else "暂无演职人员信息"

    # # 获取推荐视频信息
    # recommendations = get_recommended_videos(driver)
    # if recommendations:
    #     save_recommendations_to_csv(video_name, recommendations)

    video_info = {
        "name": video_name,
        "link": video_link,
        "poster_url": poster_url,
        "rating": rating,
        "rating_count": rating_count,
        "description": description,
        "cast": cast
    }
    return video_info

def get_recommended_videos(driver):
    """
    获取当前视频页面的推荐视频列表并获取每个推荐视频的详细信息
    :param driver: 浏览器驱动对象
    :return: 推荐视频列表（包含详细信息）
    """
    try:
        print("\n开始获取推荐视频列表...")
        
        # 等待推荐区域加载完成
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "recommend_bk"))
        )
        
        # 获取页面源码
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # 查找推荐视频列表
        recommended_videos = []
        basic_video_info = []
        
        # 1. 首先定位推荐容器
        recommend_container = soup.find('div', id='recommend_bk')
        if not recommend_container:
            print("❌ 未找到推荐视频容器")
            return []
            
        # 2. 查找所有推荐视频卡片容器
        video_cards = recommend_container.find_all('div', style=lambda x: x and 'width: 162px; height: 266px;' in x)
        print(f"📊 找到 {len(video_cards)} 个推荐视频卡片")

        # 3. 遍历卡片直到获取10个有效视频的基本信息
        valid_count = 0
        for i, card in enumerate(video_cards):
            if valid_count >= 10: ######################
                break
            
            print(f"\n🔍 正在处理第 {i+1} 个推荐视频基本信息...")
            
            try:
                # --- 1. 获取基本数据 ---
                # 视频链接（从图片或标题区域获取）
                video_link = None
                for link in card.find_all('a', href=True):
                    if link['href'].startswith(('http', '//', '/')):
                        video_link = link['href']
                        if video_link.startswith('//'):
                            video_link = 'https:' + video_link
                        elif video_link.startswith('/'):
                            video_link = 'https://www.iqiyi.com' + video_link
                        break
                
                # 视频名称
                title_span = card.find('span', class_=lambda x: x and 'title__' in x)
                video_name = title_span.get_text(strip=True) if title_span else None
                
                # 封面图片
                poster_img = card.find('img', class_=lambda x: x and 'videoImage' in x)
                poster_url = (poster_img['src'] if poster_img and poster_img.get('src') 
                             else "static/default-poster.svg")
                
                # --- 2. 数据验证 ---
                if not all([video_link, video_name]):
                    print(f"⚠️ 跳过无效卡片：缺少必要数据 | 名称:{video_name} | 链接:{video_link}")
                    continue
                
                # --- 3. 获取扩展信息 ---
                # 视频类型和集数
                type_tag = card.find('div', class_=lambda x: x and 'TypeTag' in x)
                episode_tag = card.find('div', class_=lambda x: x and 'subscript' in x)
                
                # --- 4. 构建基本视频数据 ---
                video_data = {
                    "name": video_name,
                    "link": video_link,
                    "poster_url": poster_url,
                    "type": type_tag.get_text(strip=True) if type_tag else None,
                    "episodes": episode_tag.get_text(strip=True) if episode_tag else None
                }
                
                # 添加到基本信息列表
                basic_video_info.append(video_data)
                valid_count += 1
                print(f"✅ 成功获取第 {valid_count} 个视频基本信息: {video_name}")
                
            except Exception as e:
                print(f"❌ 处理卡片基本信息时出错: {str(e)}")
                continue
        
        # 如果不足10个，尝试滚动加载更多
        scroll_attempts = 0
        while len(basic_video_info) < 10 and scroll_attempts < 3: ###################
            print(f"\n🔄 需要更多有效视频，尝试滚动加载 (尝试 {scroll_attempts+1}/3)...")
            driver.execute_script("window.scrollBy(0, 800);")
            time.sleep(2)
            
            # 重新获取卡片
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            new_cards = soup.find('div', id='recommend_bk').find_all(
                'div', style=lambda x: x and 'width: 162px; height: 266px;' in x)
            
            # 处理新增卡片的基本信息
            for card in new_cards[len(video_cards):]:
                if len(basic_video_info) >= 10:            #############
                    break
                    
                try:
                    # 获取视频链接
                    video_link = None
                    for link in card.find_all('a', href=True):
                        if link['href'].startswith(('http', '//', '/')):
                            video_link = link['href']
                            if video_link.startswith('//'):
                                video_link = 'https:' + video_link
                            elif video_link.startswith('/'):
                                video_link = 'https://www.iqiyi.com' + video_link
                            break
                    
                    # 获取视频名称
                    title_span = card.find('span', class_=lambda x: x and 'title__' in x)
                    video_name = title_span.get_text(strip=True) if title_span else None
                    
                    # 获取封面图片
                    poster_img = card.find('img', class_=lambda x: x and 'videoImage' in x)
                    poster_url = (poster_img['src'] if poster_img and poster_img.get('src') 
                                 else "static/default-poster.svg")
                    
                    if not all([video_link, video_name]):
                        continue
                    
                    # 获取类型和集数信息
                    type_tag = card.find('div', class_=lambda x: x and 'TypeTag' in x)
                    episode_tag = card.find('div', class_=lambda x: x and 'subscript' in x)
                    
                    video_data = {
                        "name": video_name,
                        "link": video_link,
                        "poster_url": poster_url,
                        "type": type_tag.get_text(strip=True) if type_tag else None,
                        "episodes": episode_tag.get_text(strip=True) if episode_tag else None
                    }
                    
                    basic_video_info.append(video_data)
                    valid_count += 1
                    print(f"✅ 成功获取第 {valid_count} 个视频基本信息: {video_name}")
                    
                except Exception as e:
                    print(f"❌ 处理新增卡片时出错: {str(e)}")
                    continue
            
            video_cards = new_cards
            scroll_attempts += 1

        print(f"\n🎯 成功获取 {len(basic_video_info)} 个视频的基本信息")
        
        # 使用线程池并行获取详细信息
        with ThreadPoolExecutor(max_workers=6) as executor:
            def get_video_details(video_data):
                try:
                    # 创建新的浏览器实例
                    detail_driver = setup_driver()
                    try:
                        # 获取详细信息
                        video_info = get_video_info(detail_driver, video_data["name"], 
                                                  video_data["link"], video_data["poster_url"], 
                                                  is_recommendation=True)
                        if video_info:
                            video_data.update({
                                "rating": video_info.get("rating"),
                                "rating_count": video_info.get("rating_count"),
                                "description": video_info.get("description"),
                                "cast": video_info.get("cast")
                            })
                        
                        # 获取评论
                        comments = get_video_comments(detail_driver, video_data["name"], video_data["link"])
                        video_data["comments"] = comments
                        
                        with print_lock:
                            print(f"✅ 成功获取 {video_data['name']} 的详细信息")
                        
                        return video_data
                    finally:
                        detail_driver.quit()
                except Exception as e:
                    with print_lock:
                        print(f"⚠️ 获取 {video_data['name']} 详细信息时出错: {str(e)}")
                    return video_data
            
            # 提交所有任务并等待完成
            future_to_video = {executor.submit(get_video_details, video): video 
                              for video in basic_video_info[:10]}         #######################
            
            for future in as_completed(future_to_video):
                try:
                    video_data = future.result()
                    if video_data:
                        recommended_videos.append(video_data)
                except Exception as e:
                    print(f"❌ 处理视频详细信息时发生错误: {str(e)}")
        
        print(f"\n🎉 完成所有视频信息获取，共 {len(recommended_videos)} 个视频")
        return recommended_videos
        
    except Exception as e:
        print(f"❌ 获取推荐视频列表时发生严重错误: {str(e)}")
        return []

def save_recommendations_to_csv(video_name, recommendations):
    """
    将推荐视频信息保存到CSV文件
    :param video_name: 主视频名称
    :param recommendations: 推荐视频列表
    """
    try:
        with file_lock:
            # 序列化评论数据
            for video in recommendations:
                if 'comments' in video:
                    try:
                        video['comments'] = json.dumps(video['comments'], ensure_ascii=False)
                    except Exception as e:
                        logging.error(f"序列化失败评论数据：{video['comments']}")
                        raise

            recommendations_df = pd.DataFrame(recommendations)
            
            # 获取当前时间并格式化为字符串
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 指定相对路径，文件名中包含当前时间
            save_path = os.path.join("data/recommendations", f"{video_name}_{current_time}.csv")
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 保存 DataFrame 到 CSV 文件
            recommendations_df.to_csv(save_path, index=False, encoding="utf-8-sig")
            logging.info(f"推荐视频信息已保存到 {save_path} 文件中。")
    except Exception as e:
        logging.error(f"保存推荐视频CSV文件时出错：{e}", exc_info=True)
        return False
    return True

def get_video_comments(driver, video_name, video_link):
    """
    获取视频的评论信息
    :param driver: 浏览器驱动对象
    :param video_name: 视频名称
    :param video_link: 视频链接
    :return: 视频评论信息列表
    """
    driver.get(video_link)
    # 等待页面完全加载
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except Exception as e:
        print(f"等待页面加载超时: {e}")
    time.sleep(3)  # 额外等待确保动态内容加载完成

    try:
        discussion_tab = driver.find_element(By.XPATH, '//div[@class="tab-menu_tabItem__VJQDn " and contains(.//div[@class="tab-menu_title__k8gOR"], "讨论")]')
        discussion_tab.click()
        print(f"成功切换到讨论标签页")
        # 等待讨论内容加载
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[id^="comment"]'))
            )
        except Exception as e:
            print(f"等待讨论内容加载超时: {e}")
    except Exception as e:
        print(f"无法点击讨论标签：{e}")
        return [{"nickname": "", "user_id": "", "avatar_url": "", "comment_time": "", "comment_content": "", "like_count": ""}]
    time.sleep(3)  # 额外等待确保评论内容完全加载

    discussion_page_source = driver.page_source
    discussion_soup = BeautifulSoup(discussion_page_source, 'html.parser')

    comment_divs = discussion_soup.select('div[id^="comment"]')[:10]

    comments = []
    for index, comment_div in enumerate(comment_divs):
        try:
            # 检查是否存在展开按钮
            expand_button = comment_div.find('div', class_='collapse-text_expandBtn__R7Ga3 comments_commentCollasepBtn__3OMXE')
            if expand_button:
                print(f"发现展开按钮，正在尝试点击展开第 {index + 1} 条评论")
                # 模拟点击展开按钮
                expand_button_element = driver.find_element(By.XPATH, f'//div[@id="comment{comment_div["id"].split("comment")[-1]}"]//div[contains(@class, "collapse-text_expandBtn__R7Ga3")]')
                driver.execute_script("arguments[0].click();", expand_button_element)
                time.sleep(2)  # 增加等待时间，确保评论内容完全展开
                print(f"成功展开第 {index + 1} 条评论")
                discussion_page_source = driver.page_source
                discussion_soup = BeautifulSoup(discussion_page_source, 'html.parser')
                # 重新获取当前评论的 div
                comment_div = discussion_soup.select_one(f'div[id="{comment_div["id"]}"]')

            # 获取评论人头像和用户ID
            avatar_box = comment_div.find('div', class_='comments_avatarBox__7xweF')
            avatar_img = avatar_box.find('img', class_='comments_avatar__FU5C5')
            avatar_url = avatar_img['src'] if avatar_img else None
            user_id = re.search(r'passport_(\d+)', avatar_url).group(1) if avatar_url else None

            # 获取评论内容
            nickname_element = comment_div.find('div', class_=re.compile(r'^comments_name__VQiPd'))
            nickname = nickname_element.get_text(strip=True)

            comment_time_element = comment_div.find('div', class_='comments_time__00lty')
            comment_time = comment_time_element.get_text(strip=True)

            comment_content_element = comment_div.find('div', class_='collapse-text_collapseText__zVrd2 comments_commentText__D48oR')
            comment_content = comment_content_element.get_text(strip=True)

            like_count_element = comment_div.find('span', id='text')
            like_count = like_count_element.get_text(strip=True)

            if nickname and comment_time and comment_content and like_count:
                comments.append({
                    "nickname": nickname,
                    "user_id": user_id,
                    "avatar_url": avatar_url,
                    "comment_time": comment_time,
                    "comment_content": comment_content,
                    "like_count": like_count
                })
        except Exception as e:
            print(f"\"{video_name}\"在提取第 {index + 1} 条评论信息时出错：{e}")
            continue

    return comments

def save_to_csv(details):
    """
    将视频详情信息保存到 CSV 文件
    :param details: 视频详情信息列表
    """
    try:
        with file_lock:
            # 序列化评论数据
            for detail in details:
                if 'comments' in detail:
                    try:
                        detail['comments'] = json.dumps(detail['comments'], ensure_ascii=False)
                    except Exception as e:
                        logging.error(f"序列化失败评论数据：{detail['comments']}")
                        raise

            details_df = pd.DataFrame(details)
            
            # 获取当前时间并格式化为字符串
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 指定相对路径，文件名中包含当前时间
            save_path = os.path.join("data/hotdata", f"iqiyi_{current_time}.csv")
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 保存 DataFrame 到 CSV 文件
            details_df.to_csv(save_path, index=False, encoding="utf-8-sig")
            logging.info(f"视频详情信息已保存到 {save_path} 文件中。")
    except Exception as e:
        logging.error(f"保存CSV文件时出错：{e}", exc_info=True)
        return False
    return True

# 全局会话对象，提升连接池容量，减少连接被丢弃
session = requests.Session()
session.mount('http://', requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20))
session.mount('https://', requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20))
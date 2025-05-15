import os
import re
import csv
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

def setup_driver(headless=False):
    """
    配置并启动 Chrome 浏览器驱动
    :return: 浏览器驱动对象
    """
    chrome_options = Options()
    chrome_options.add_argument("--ignore-certificate-errors")
    # if headless:
    #     chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--log-level=3")  # 3 表示只显示 FATAL 级别的日志

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

def click_hottest_tab(driver):
    """
    点击爱奇艺首页的“最热”标签
    :param driver: 浏览器驱动对象
    """
    try:
        hottest_tab = driver.find_element(By.XPATH, '//div[@data-role="button" and contains(.//span, "最热")]')
        hottest_tab.click()
    except Exception as e:
        print(f"无法找到或点击最热标签：{e}")
    time.sleep(1)

def get_video_list(driver):
    """
    获取“最热”标签下的视频列表
    :param driver: 浏览器驱动对象
    :return: 视频列表，包含视频名称和链接
    """
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')

    # 查找视频卡片
    video_cards = soup.find_all('div', class_='flex-video-list_flexTilesItem__bhNS9')
    videos = []

    for card in video_cards[:4]:
        # 提取视频名称
        video_name_tag = card.find('p', class_='undefined flex-video-list_title__pTUUg')
        video_name = video_name_tag.get_text(strip=True) if video_name_tag else None
        
        # 提取视频链接
        parent_link = card.find('a')
        video_link = parent_link['href'] if parent_link and parent_link.get('href') else None
        
        # 提取封面图片链接
        poster_img = card.find('img', class_='flex-video-list_poster__cNMg+')
        poster_url = poster_img['src'] if poster_img and poster_img.get('src') else None
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

def get_video_info(driver, video_name, video_link, poster_url):
    """
    获取单个视频的基本信息，包括评分次数、简介、演员表
    :param driver: 浏览器驱动对象
    :param video_name: 视频名称
    :param video_link: 视频链接
    :return: 视频基本信息
    """
    driver.get(video_link)
    time.sleep(1)

    try:
        detail_button = driver.find_element(By.XPATH, '//div[@class="meta_arrowBtn__gw1b5 meta_detailBtn__2XYRK"]')
        detail_button.click()
    except Exception as e:
        print(f"无法点击详情按钮：{e}")
        return None
    time.sleep(1)

    detail_page_source = driver.page_source
    detail_soup = BeautifulSoup(detail_page_source, 'html.parser')

    rating_count = detail_soup.find('div', class_='score_scoreCount__aNzvS').get_text(strip=True) if detail_soup.find(
        'div', class_='score_scoreCount__aNzvS') else "未知"
    description = detail_soup.find('div', class_='metaDetail_infoValue__NNS+T').get_text(strip=True) if detail_soup.find(
        'div', class_='metaDetail_infoValue__NNS+T') else "无简介"
    cast_list = detail_soup.find_all('div', class_='star-list_name__VSd6I')
    cast = ", ".join([cast.get_text(strip=True) for cast in cast_list]) if cast_list else "无演员表"

    video_info = {
        "name": video_name,
        "link": video_link,
        "poster_url": poster_url,
        "rating_count": rating_count,
        "description": description,
        "cast": cast
    }
    return video_info

def get_video_comments(driver, video_name, video_link):
    """
    获取视频的评论信息
    :param driver: 浏览器驱动对象
    :param video_name: 视频名称
    :param video_link: 视频链接
    :return: 视频评论信息列表
    """
    driver.get(video_link)
    time.sleep(1)

    try:
        discussion_tab = driver.find_element(By.XPATH, '//div[@class="tab-menu_tabItem__VJQDn " and contains(.//div[@class="tab-menu_title__k8gOR"], "讨论")]')
        discussion_tab.click()
        print(f"成功切换到讨论标签页")
    except Exception as e:
        print(f"无法点击讨论标签：{e}")
        return []
    time.sleep(1)

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
                time.sleep(1)  # 等待评论内容加载
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
    details_df = pd.DataFrame(details)
    
    # 获取当前时间并格式化为字符串
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 指定相对路径，文件名中包含当前时间
    save_path = os.path.join("data", f"iqiyi_{current_time}.csv")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)  # 如果目录不存在，自动创建
    
    # 保存 DataFrame 到 CSV 文件
    details_df.to_csv(save_path, index=False, encoding="utf-8-sig")
    print(f"视频详情信息已保存到 {save_path} 文件中。")



def get_video_comments(video_name, video_link):
    """
    获取视频的评论信息（内部自行管理浏览器驱动）
    :param video_name: 视频名称
    :param video_link: 视频链接
    :return: 视频评论信息列表
    """
    # from selenium.webdriver.common.by import By
    # from selenium.webdriver.support.ui import WebDriverWait
    # from selenium.webdriver.support import expected_conditions as EC
    # from bs4 import BeautifulSoup
    # import re
    
    print(f"\n正在获取视频 '{video_name}' 的评论...")
    
    # 初始化浏览器驱动
    driver = None
    try:
        driver = setup_driver(headless=True)  # 使用无头模式
        driver.get(video_link)
        time.sleep(2)
        
        # 自动登录
        outo_login(driver)
        # time.sleep(2)
        
        # # 访问视频页面
        # driver.get(video_link)
        # time.sleep(3)
        
        # 切换到讨论标签页
        try:
            discussion_tab = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//div[@class="tab-menu_tabItem__VJQDn " and contains(.//div[@class="tab-menu_title__k8gOR"], "讨论")]'))
            )
            driver.execute_script("arguments[0].click();", discussion_tab)
            print("成功切换到讨论标签页")
            time.sleep(3)
        except Exception as e:
            print(f"无法点击讨论标签：{e}")
            return []
        
        # 获取页面源码并解析
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
                    expand_button_element = driver.find_element(By.XPATH, f'//div[@id="comment{comment_div["id"].split("comment")[-1]}"]//div[contains(@class, "collapse-text_expandBtn__R7Ga3")]')
                    driver.execute_script("arguments[0].click();", expand_button_element)
                    time.sleep(1)
                    print(f"成功展开第 {index + 1} 条评论")
                    discussion_page_source = driver.page_source
                    discussion_soup = BeautifulSoup(discussion_page_source, 'html.parser')
                    comment_div = discussion_soup.select_one(f'div[id="{comment_div["id"]}"]')

                # 获取评论人信息
                avatar_box = comment_div.find('div', class_='comments_avatarBox__7xweF')
                avatar_img = avatar_box.find('img', class_='comments_avatar__FU5C5') if avatar_box else None
                avatar_url = avatar_img['src'] if avatar_img else None
                user_id = re.search(r'passport_(\d+)', avatar_url).group(1) if avatar_url else None

                # 获取评论内容
                nickname_element = comment_div.find('div', class_=re.compile(r'^comments_name__VQiPd'))
                nickname = nickname_element.get_text(strip=True) if nickname_element else "匿名用户"

                comment_time_element = comment_div.find('div', class_='comments_time__00lty')
                comment_time = comment_time_element.get_text(strip=True) if comment_time_element else "未知时间"

                comment_content_element = comment_div.find('div', class_='collapse-text_collapseText__zVrd2 comments_commentText__D48oR')
                comment_content = comment_content_element.get_text(strip=True) if comment_content_element else "无内容"

                like_count_element = comment_div.find('span', id='text')
                like_count = like_count_element.get_text(strip=True) if like_count_element else "0"

                comments.append({
                    "user_name": nickname,
                    "user_id": user_id,
                    "avatar_url": avatar_url,
                    "comment_time": comment_time,
                    "content": comment_content,
                    "likes": like_count
                })
            except Exception as e:
                print(f"提取第 {index + 1} 条评论信息时出错：{e}")
                continue
        
        return comments
        
    except Exception as e:
        print(f"获取评论时发生错误: {e}")
        return []
    finally:
        if driver:
            driver.quit()
            print("浏览器驱动已关闭")

def save_recommendations_to_csv(driver,video_name, recommendations):
    """
    保存推荐视频信息到CSV文件
    :param video_name: 原始视频名称
    :param recommendations: 推荐视频列表
    """
    if not recommendations:
        print("没有推荐视频数据可保存")
        return
    
    # import csv
    # from datetime import datetime
    
    # 确保目录存在
    os.makedirs("data/recommend", exist_ok=True)
    
    # 清理文件名中的非法字符
    safe_name = "".join([c for c in video_name if c.isalpha() or c.isdigit() or c in (' ', '_')]).rstrip()
    filename = f"data/recommend/{safe_name}_猜你喜欢.csv"
    
    # 定义CSV字段
    fieldnames = [
        "推荐视频名称", "视频链接", "海报链接", "点赞次数", "简介", 
        "演员表", "评论人ID", "评论人昵称", "评论时间", "评论内容", "评论点赞数"
    ]
    
    try:
        with open(filename, mode='w', encoding='utf-8-sig', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            
            for rec in recommendations:
                # 获取视频详细信息
                video_info = get_video_info(driver, rec['name'], rec['link'], rec['poster_url'])
                if not video_info:
                    continue
                
                # 获取视频评论
                comments = get_video_comments(driver, rec['name'], rec['link'])
                
                # 如果没有评论，至少写入一条基本信息
                if not comments:
                    writer.writerow({
                        "推荐视频名称": rec['name'],
                        "视频链接": rec['link'],
                        "海报链接": rec['poster_url'],
                        "点赞次数": video_info.get('likes', ''),
                        "简介": video_info.get('description', ''),
                        "演员表": video_info.get('actors', '')
                    })
                else:
                    # 写入每条评论作为单独行
                    for comment in comments[:10]:  # 只取前10条评论
                        writer.writerow({
                            "推荐视频名称": rec['name'],
                            "视频链接": rec['link'],
                            "海报链接": rec['poster_url'],
                            "点赞次数": video_info.get('likes', ''),
                            "简介": video_info.get('description', ''),
                            "演员表": video_info.get('actors', ''),
                            "评论人ID": comment.get('user_id', ''),
                            "评论人昵称": comment.get('user_name', ''),
                            "评论时间": comment.get('comment_time', ''),
                            "评论内容": comment.get('content', ''),
                            "评论点赞数": comment.get('likes', '')
                        })
        
        print(f"推荐视频数据已保存到 {filename}")
    except Exception as e:
        print(f"保存推荐视频数据时出错: {e}")
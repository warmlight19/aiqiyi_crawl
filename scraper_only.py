import os
import time
# import json
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
import scraper

def main():
    # 1. 设置浏览器驱动
    print("正在启动浏览器...")
    driver = scraper.setup_driver(headless=False)  # 设置为True可以无头模式运行
    
    try:
        # 2. 访问爱奇艺首页并登录
        print("正在访问爱奇艺首页...")
        driver.get("https://www.iqiyi.com/")
        time.sleep(2)
        
        print("正在尝试登录...")
        scraper.outo_login(driver)
        time.sleep(2)
        
        # 3. 点击"最热"标签
        print("正在切换到最热标签...")
        scraper.click_hottest_tab(driver)
        time.sleep(2)
        
        # 4. 获取视频列表
        print("正在获取视频列表...")
        videos = scraper.get_video_list(driver)
        if not videos:
            print("未获取到视频列表，程序终止")
            return
        
        print(f"共获取到 {len(videos)} 个视频:")
        for i, video in enumerate(videos, 1):
            print(f"{i}. {video['name']}")
        
        # 5. 获取每个视频的详细信息和评论
        all_details = []
        
        for video in videos:
            print(f"\n正在处理视频: {video['name']}")
            
            # 获取视频基本信息
            print("正在获取视频基本信息...")
            video_info = scraper.get_video_info(driver, video['name'], video['link'], video['poster_url'])
            if not video_info:
                print(f"无法获取视频 {video['name']} 的基本信息，跳过")
                continue
            
            # 获取视频评论
            print("正在获取视频评论...")
            comments = scraper.get_video_comments(driver, video['name'], video['link'])
            video_info['comments'] = comments
            print(f"获取到 {len(comments)} 条评论")
            
            all_details.append(video_info)
            time.sleep(1)
        
        # 6. 保存结果到CSV
        if all_details:
            print("\n正在保存结果...")
            scraper.save_to_csv(all_details)
            print("数据保存完成！")
        else:
            print("没有获取到有效数据，不进行保存")
    
    except Exception as e:
        print(f"程序运行出错: {e}")
    finally:
        # 关闭浏览器
        driver.quit()
        print("浏览器已关闭")

if __name__ == "__main__":
    main()
from selenium import webdriver
import json
import time

# 打开爱奇艺网站
driver = webdriver.Chrome()
driver.get("https://www.iqiyi.com/")

# 加载保存的Cookie
with open('iqiyi_cookies.json', 'r') as f:
    cookies = json.load(f)

# 添加Cookie到当前会话
for cookie in cookies:
    driver.add_cookie(cookie)

# 刷新页面以应用Cookie
driver.refresh()
time.sleep(10)

print("自动登录成功！")
from selenium import webdriver
import json

# 打开爱奇艺网站
driver = webdriver.Chrome()
driver.get("https://www.iqiyi.com/")

# 等待手动登录
input("登录成功后，请在控制台输入任意内容继续...")

# 获取当前页面的Cookie
cookies = driver.get_cookies()

# 将Cookie保存到本地文件
with open('iqiyi_cookies.json', 'w') as f:
    json.dump(cookies, f)

print("Cookie保存成功！")
driver.quit()
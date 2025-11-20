import requests
import fake_useragent
from bs4 import BeautifulSoup #

#создаём фейк пользователя
user = fake_useragent.UserAgent().random
header = {'user-agent': user}


link = 'https://browser-info.ru/' 
res = requests.get(link, headers = header).text
soup = BeautifulSoup(res, 'lxml')
info = soup.find('div', id = 'tool_padding')

js = info.find('div', id = 'javascript_check')
js2 = js.find_all('span')[1].text
js3 = f'javascript: {js2}'

flash = info.find('div', id = 'flash_version')
flash2 = flash.find_all('span')[1].text
flash3 = f'flash: {flash2}'

usag = info.find('div', id = 'user_agent').text

print(js3, flash3, usag)
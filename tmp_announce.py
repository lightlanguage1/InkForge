import json, urllib.request

body = json.dumps({"display_name":"admin","password":"admin123"}).encode()
req = urllib.request.Request("http://127.0.0.1:9000/api/v1/auth/login", data=body, headers={"Content-Type":"application/json"})
resp = urllib.request.urlopen(req)
token = json.loads(resp.read())["token"]
print(f"Token: {token[:30]}...")

ann = json.dumps({
    "title": "\U0001f3b5 音乐播放器已升级为本地播放",
    "content": "音乐模块已从在线API源切换为本地文件播放器。\n\n点击播放器面板中的「\U0001f4c1 选择文件夹」按钮，选择你电脑上的音乐文件夹即可播放。收藏通过浏览器本地存储，无需登录。移动端支持多文件选择。\n\n如有问题请反馈。",
    "tag": "更新"
}).encode()
req2 = urllib.request.Request("http://127.0.0.1:9000/api/v1/announcements/", data=ann, headers={"Content-Type":"application/json", "Authorization": f"Bearer {token}"})
resp2 = urllib.request.urlopen(req2)
print(json.loads(resp2.read()))

# encoding=utf8
import requests
import json
import time
import datetime
import pytz
import re
import sys
import argparse
from bs4 import BeautifulSoup
import cv2 as cv
import pytesseract
from PIL import Image
import numpy



#识别验证码
def recognize_text(img):
    gray_img = cv.cvtColor(img, cv.COLOR_RGB2GRAY) #灰度图
    height, width = gray_img.shape #获取图片宽高
    (_, blur_img) = cv.threshold(gray_img, 127, 255, cv.THRESH_BINARY) #二值化 固定阈值127 

    #ROI掩模区域反向掩模
    mask_inv = cv.bitwise_not(blur_img)

    #掩模显示前景
    # Take only region of logo from logo image.
    img2_fg = cv.bitwise_and(img,img,mask = mask_inv)

    # 灰度图像
    gray = cv.cvtColor(img2_fg, cv.COLOR_BGR2GRAY)

    # 二值化
    ret, binary = cv.threshold(gray, 0, 255, cv.THRESH_BINARY_INV | cv.THRESH_OTSU)

    # 识别
    test_message = Image.fromarray(binary)
    text = pytesseract.image_to_string(test_message)
    #print('识别结果：%s' % text)

    return text

class Report(object):
    def __init__(self, stuid, password, data_path, dorm):
        self.stuid = stuid
        self.password = password
        self.data_path = data_path
        self.dorm = dorm

    def report(self):
        loginsuccess = False
        retrycount = 5
        while (not loginsuccess) and retrycount:
            session = self.login()
            cookies = session.cookies
            getform = session.get("https://weixine.ustc.edu.cn/2020")
            retrycount = retrycount - 1
            if getform.url != "https://weixine.ustc.edu.cn/2020/home":
                print("Login Failed! Retry...")
            else:
                print("Login Successful!")
                loginsuccess = True
        if not loginsuccess:
            return False
        data = getform.text
        data = data.encode('ascii','ignore').decode('utf-8','ignore')
        soup = BeautifulSoup(data, 'html.parser')
        token = soup.find("input", {"name": "_token"})['value']

        with open(self.data_path, "r+") as f:
            data = f.read()
            data = json.loads(data)
            data["_token"]=token
            data["dorm"]=self.dorm


        headers = {
            'authority': 'weixine.ustc.edu.cn',
            'origin': 'https://weixine.ustc.edu.cn',
            'upgrade-insecure-requests': '1',
            'content-type': 'application/x-www-form-urlencoded',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.100 Safari/537.36',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'referer': 'https://weixine.ustc.edu.cn/2020/',
            'accept-language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',
        }

        url = "https://weixine.ustc.edu.cn/2020/daliy_report"

        post_data=session.post(url, data=data, headers=headers)
        flag = True if post_data.text.find("上报成功")!=-1 else False

        pattern = re.compile("[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")
        if flag == False:
            print("Report FAILED!")
        else:
            flag = False
            print("Report SUCCESSFUL!")

            # 离校报备
            getform = session.get("https://weixine.ustc.edu.cn/2020/apply/daliy/i?t=23")
            data = getform.text
            data = data.encode('ascii','ignore').decode('utf-8','ignore')
            soup = BeautifulSoup(data, 'html.parser')
            token = soup.find("input", {"name": "_token"})['value']
            start_date = soup.find("input", {"id": "start_date"})['value']
            end_date = soup.find("input", {"id": "end_date"})['value']

            url = "https://weixine.ustc.edu.cn/2020/apply/daliy/post"
            data2={}
            data2["_token"]=token
            data2["start_date"]=start_date
            data2["end_date"]=end_date
            data2["return_college[]"]=["东校区","西校区","中校区"]
            data2["reason"]="上课"
            data2["t"]="23"

            post_data=session.post(url, data=data2, headers=headers)
            data = session.get("https://weixine.ustc.edu.cn/2020/apply_total?t=d").text

            soup = BeautifulSoup(data, 'html.parser')
            date = soup.find(text=pattern)
            if data:
                print("Latest apply: " + date)
                date = date + " +0800"
                reporttime = datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S %z")
                timenow = datetime.datetime.now(pytz.timezone('Asia/Shanghai'))
                delta = timenow - reporttime
                print("{} second(s) before.".format(delta.seconds))
                if delta.seconds < 120:
                    flag = True
                if flag == False:
                    print("Apply FAILED!")
                else:
                    print("Apply SUCCESSFUL!")
        return flag

    def login(self):
        url = "https://passport.ustc.edu.cn/login?service=http%3A%2F%2Fweixine.ustc.edu.cn%2F2020%2Fcaslogin"
        validatecode_url = "https://passport.ustc.edu.cn/validatecode.jsp?type=login"
        data = {
            'model': 'uplogin.jsp',
            'service': 'http://weixine.ustc.edu.cn/2020/caslogin',
            'username': self.stuid,
            'password': str(self.password),
            'warn' : '',
            'showCode' : '1',
        }
        session = requests.Session()

        res_get = session.get(url)

        html_data = res_get.text
        #print(html_data)
        html_data = html_data.encode('ascii','ignore').decode('utf-8','ignore')
        soup = BeautifulSoup(html_data, 'html.parser')
        CAS_LT = soup.find("input", {"name": "CAS_LT"})['value']#我也不知道这个东西有什么用
        data["CAS_LT"]=CAS_LT
        
        validatecode_img = session.get(validatecode_url)


        image = numpy.asarray(bytearray(validatecode_img.content), dtype="uint8")
        image = cv.imdecode(image, cv.IMREAD_COLOR)#验证码图片

        validatecode = recognize_text(image)
        data["LT"] = re.findall("\d+",validatecode)[0]

        res_post = session.post(url, data=data)

        print("login...")
        return session


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='URC nCov auto report script.')
    parser.add_argument('data_path', help='path to your own data used for post method', type=str)
    parser.add_argument('stuid', help='your student number', type=str)
    parser.add_argument('password', help='your CAS password', type=str)
    parser.add_argument('dorm', help='your dorm', type=str)
    args = parser.parse_args()
    autorepoter = Report(stuid=args.stuid, password=args.password, data_path=args.data_path,dorm=args.dorm)
    count = 5
    while count != 0:
        ret = autorepoter.report()
        if ret != False:
            break
        print("Report Failed, retry...")
        count = count - 1
    if count != 0:
        exit(0)
    else:
        exit(-1)

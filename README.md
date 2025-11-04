# 🌐 Telegram 群组内容监控系统 - TelScan
[![公众号](https://img.shields.io/badge/公众号-白昼信安-da282a)](https://your-wechat-link.com) [![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)  [![Flask](https://img.shields.io/badge/Flask-2.3+-green.svg)](https://flask.palletsprojects.com/)[![Version](https://img.shields.io/badge/Version-2.0-orange.svg)](https://github.com/wxwhhh/TelScan)
[![Update](https://img.shields.io/badge/Update-2025.11.04-brightgreen.svg)](https://github.com/wxwhhh/TelScan)

#### 1、平台介绍
平台调用telegram API对已加入的群组、频道或者是公开的群组、频道内容进行实时监控，然后web展示以及钉钉、企业微信通知。
<img width="2553" height="1270" alt="image" src="https://github.com/user-attachments/assets/fbaa7d40-e318-43c8-ab89-03c21e5762ca" />


#### 2、平台功能 -- 系统配置
先进行系统配置，输入申请的API、手机号、钉钉后进行保存即可。
<img width="1273" height="633" alt="2" src="https://github.com/user-attachments/assets/0d73bab6-548d-4af9-a409-0df224fbd3f9" />

#### 3、平台功能 -- 群组管理
群组管理这边有三个功能
<img width="1280" height="483" alt="3" src="https://github.com/user-attachments/assets/3249bc75-22ca-42ed-b4db-41c81d8bc5d5" />

**一是**批量添加群组，你只需要将你要添加的群组的链接整理一下，一行一个，然后粘贴进去，设置延迟时间即可自动化加群。
<img width="1267" height="460" alt="4" src="https://github.com/user-attachments/assets/82033383-2fb2-4933-8c82-09dd962e6956" />
<img width="1279" height="358" alt="5" src="https://github.com/user-attachments/assets/2bfa8ff0-ed6e-4c75-9eb7-769c771f6181" />
**二是**获取目前账号加入的全部群组，然后选择是否对群组进行监听。
<img width="1064" height="190" alt="6" src="https://github.com/user-attachments/assets/46dc91af-429d-46a8-a2ec-d68d4eca00c6" />
<img width="982" height="150" alt="7" src="https://github.com/user-attachments/assets/70d61b2d-b6bc-45c6-b9be-bba2a49a1021" />
<img width="998" height="380" alt="8" src="https://github.com/user-attachments/assets/8b0db59e-ce16-4a71-ba64-7c7423126068" />
**三是**手动添加群组，输入群组的链接地址，然后添加并监听。
<img width="969" height="215" alt="9" src="https://github.com/user-attachments/assets/061bc948-e6d9-4a87-b74e-b4eff97e7306" />
#### 4、平台功能 -- 关键词管理
必须在添加监控群组后才可以添加监听关键词，然后输入要监听的关键词，选择要关键词监听群组(可多选)然后保存就可以了。(可一次添加多个关键词，一行一个)
<img width="1792" height="849" alt="image" src="https://github.com/user-attachments/assets/7ca13fa2-8f49-4cd6-a7f3-ba1ec006b059" />

#### 5、平台功能 -- 消息日志
监听到的信息会在这里展示，包括时间、发消息任意、群组等信息，上面还有筛选功能数据过多时可以进行筛选，同时配置钉钉的话就会同步发送，及时掌握消息。
<img width="1275" height="369" alt="10" src="https://github.com/user-attachments/assets/f04f7fc5-7e88-4a7c-8c42-c6a42f094e86" />
<img width="554" height="143" alt="11" src="https://github.com/user-attachments/assets/cdf68675-06f1-4f35-9789-d262b1f46bc8" />

# 🧐 搭建教程
- 前往 [Telegram 官方](https://my.telegram.org) 注册  
先去注册一个telegram API，网上有教程搜一下，此外如果注册api一直报ERROR的话，狂点**创建应用程序**按钮即可成功。
环境使用的是python和mysql环境
<img width="804" height="410" alt="12" src="https://github.com/user-attachments/assets/b8977eea-3606-42dd-8486-e39f0ecf9517" />

第一步：py环境自己安装哈，mysql数据库可以使用setup_mysql.sh脚本一键安装mysql数据库及创建默认数据库。
<img width="574" height="539" alt="13" src="https://github.com/user-attachments/assets/926d67f7-b421-4175-810d-c889c9797de6" />

第二步：pip源码下来，然后安装需要的库

`git clone https://github.com/wxwhhh/TelScan.git`

`cd TelScan`

此外要使用图片关键词识别的话，要单独安装Tesseract OCR，命令如下:

Ubuntu/Debian系统：
```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-chi-sim
```

CentOS/RHEL系统：
```bash
sudo yum install -y epel-release
sudo yum install -y tesseract tesseract-langpack-chi-sim
```

第三步：启动环境  python3 app.py
<img width="836" height="177" alt="14" src="https://github.com/user-attachments/assets/002db866-bad5-4feb-ab4d-d39b66490b16" />

第四步：第一次需要你输入你的配置信息telegram 的 id hash 手机号等信息，然后telegram为了安全会给你的telegram号发一个以验证码，输入就行了，然后就IP地址+8033端口，开始使用！！！
<img width="674" height="130" alt="15" src="https://github.com/user-attachments/assets/4d39e337-5659-4c36-95f0-4af331840471" />
<img width="1108" height="163" alt="16" src="https://github.com/user-attachments/assets/e36fec9a-7cba-4c2f-9e32-0e5c9b3249b6" />
<img width="524" height="205" alt="17" src="https://github.com/user-attachments/assets/06111089-16f1-4e9c-8332-12f15fe6b4d9" />

## ⚠️ 使用声明

- 本项目仅用于 **学习研究** 与 **安全测试**，请勿将其用于任何非法用途。  
- 严禁任何形式的 **倒卖、二次收费分发或商用行为**。  
- 使用本项目可能涉及 **监控、收集、存储第三方数据**，请严格遵守当地法律法规，避免触碰法律红线。  
- 因使用本项目所产生的 **法律责任与风险**，均由使用者本人承担，作者不对任何直接或间接损失负责。  
- 下载或使用本项目代码，即视为已接受以上条款。  

#### 欢迎使用师傅们关注交流
<img width="562" height="210" alt="Snipaste_2025-08-13_11-10-04" src="https://github.com/user-attachments/assets/94dab6f4-640c-4458-9edd-3e90ead27b4d" />

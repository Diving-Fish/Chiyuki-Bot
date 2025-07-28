# Chiyuki Bot 使用指南

此 README 提供了最低程度的 Chiyuki Bot 教程与支持。

**建议您至少拥有一定的编程基础之后再尝试使用本工具。**

## Step 1. 安装 Python

请自行前往 https://www.python.org/ 下载 Python 3 版本（> 3.10）并将其添加到环境变量（在安装过程中勾选 Add Python to system PATH）。对大多数用户来说，您应该下载 Windows installer (64-bit)。

在 Linux 系统上，可能需要其他方法安装 Python 3，请自行查找。

## Step 2. 运行项目

建议使用 git 对此项目进行版本管理。您也可以直接在本界面下载代码的压缩包进行运行。

在运行代码之前，您需要从[此链接](https://www.diving-fish.com/chiyukibot/static.zip)下载资源文件并解压到`src`文件夹中。

> 资源文件仅供学习交流使用，请自觉在下载 24 小时内删除资源文件。

在此之后，**您需要打开控制台，并切换到该项目所在的目录。**
在 Windows 10 系统上，您可以直接在项目的根目录（即 bot.py）文件所在的位置按下 Shift + 右键，点击【在此处打开 PowerShell 窗口】。
如果您使用的是更旧的操作系统（比如 Windows 7），请自行查找关于`Command Prompt`，`Powershell`以及`cd`命令的教程。

之后，在打开的控制台中输入
```
python --version
```
控制台应该会打印出 Python 的版本。如果提示找不到 `python` 命令，请检查环境变量或干脆重装 Python，**并务必勾选 Add Python to system PATH**。

之后，输入
```
pip install -r requirements.txt
```
安装依赖完成后，运行
```
python bot.py
```
运行项目。如果输出如下所示的内容，代表运行成功：
```
08-02 11:26:48 [INFO] nonebot | NoneBot is initializing...
08-02 11:26:48 [INFO] nonebot | Current Env: prod
08-02 11:26:49 [INFO] nonebot | Succeeded to import "maimaidx"
08-02 11:26:49 [INFO] nonebot | Succeeded to import "public"
08-02 11:26:49 [INFO] nonebot | Running NoneBot...
08-02 11:26:49 [INFO] uvicorn | Started server process [5268]
08-02 11:26:49 [INFO] uvicorn | Waiting for application startup.
08-02 11:26:49 [INFO] uvicorn | Application startup complete.
08-02 11:26:49 [INFO] uvicorn | Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```
**运行成功后请勿关闭此窗口，后续需要与前端 QQ Bot 服务连接。**

## Step 3. 连接 

本 bot 基于协议 [Onebot v11](https://github.com/botuniverse/onebot-11)，您可以选择任意支持 Onebot 协议的前端实现，具体可以参考[这个章节](https://onebot.dev/ecosystem.html#onebot-11-10-cqhttp)

请参考您选择的前端实现配置**反向 Websocket** 链接到 8000 端口，并设置 Access Token（此 bot 在 0.0.0.0:8000 提供服务，配置 8000 端口的防火墙也可）

## 说明

请自行使用【插件管理】和【help】指令获取插件说明

## License

MIT

您可以自由使用本项目的代码用于商业或非商业的用途，但必须附带 MIT 授权协议。

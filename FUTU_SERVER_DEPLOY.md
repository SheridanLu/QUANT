# 富途OpenD服务器部署指南

## 方案概述

### 方案A：服务器安装OpenD（推荐）
- OpenD运行在你的服务器上
- 策略代码也运行在服务器上
- 7x24小时运行

### 方案B：本地OpenD + 服务器策略
- OpenD运行在你本地电脑
- 服务器通过网络连接本地OpenD
- 本地需要一直开机

---

## 方案A：服务器部署OpenD（推荐）

### 步骤1：下载OpenD

```bash
# 登录你的服务器
ssh root@your-server

# 创建目录
mkdir -p /opt/futu
cd /opt/futu

# 下载Linux版OpenD
wget https://softwarefile.futunn.com/futuquant/OpenD/OpenD_8.2.3208_Linux.tar.gz

# 解压
tar -xzf OpenD_8.2.3208_Linux.tar.gz

# 进入目录
cd OpenD
```

### 步骤2：配置OpenD

创建配置文件 `OpenD.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<config>
    <api_svr>
        <web_port>11111</web_port>
    </api_svr>
    <login>
        <account>你的富途账号</account>
        <password>你的密码（MD5加密）</password>
    </login>
</config>
```

**获取MD5密码**:
```bash
echo -n "你的密码" | md5sum
```

### 步骤3：运行OpenD

```bash
# 给执行权限
chmod +x OpenD

# 运行
./OpenD

# 或者后台运行
nohup ./OpenD > opend.log 2>&1 &
```

### 步骤4：验证

```bash
# 检查是否运行
ps aux | grep OpenD

# 检查端口
netstat -tlnp | grep 11111
```

### 步骤5：测试连接

```bash
# 安装Python库
pip3 install futu-api

# 测试脚本
python3 << 'EOF'
from futu import *

quote_ctx = OpenQuoteContext('127.0.0.1', 11111)
ret, data = quote_ctx.get_market_snapshot(['HK.00700'])

if ret == RET_OK:
    print("✓ 连接成功!")
    print(data)
else:
    print("✗ 连接失败:", data)
EOF
```

---

## 方案B：本地OpenD + 服务器连接

### 步骤1：本地运行OpenD

1. 下载Windows/Mac版OpenD
2. 登录你的富途账号
3. 保持运行

### 步骤2：配置外网访问

**方法1：使用ngrok（简单）**

```bash
# 本地安装ngrok
# 运行
ngrok tcp 11111

# 会得到一个地址，比如：tcp://0.tcp.ngrok.io:12345
```

**方法2：路由器端口转发**

需要：
- 公网IP
- 路由器配置端口转发 11111 -> 本地IP

### 步骤3：服务器连接

修改服务器上的代码：
```python
# 从
quote_ctx = OpenQuoteContext('127.0.0.1', 11111)

# 改为
quote_ctx = OpenQuoteContext('0.tcp.ngrok.io', 12345)  # ngrok地址
```

---

## 自动化部署脚本

我给你写个一键部署脚本：

```bash
#!/bin/bash
# futu_deploy.sh

echo "===== 富途OpenD自动部署 ====="

# 1. 安装依赖
echo "[1/5] 安装依赖..."
apt-get update
apt-get install -y wget python3-pip
pip3 install futu-api

# 2. 下载OpenD
echo "[2/5] 下载OpenD..."
mkdir -p /opt/futu
cd /opt/futu

if [ ! -f "OpenD_8.2.3208_Linux.tar.gz" ]; then
    wget https://softwarefile.futunn.com/futuquant/OpenD/OpenD_8.2.3208_Linux.tar.gz
fi

# 3. 解压
echo "[3/5] 解压..."
tar -xzf OpenD_8.2.3208_Linux.tar.gz
cd OpenD
chmod +x OpenD

# 4. 创建systemd服务
echo "[4/5] 创建服务..."
cat > /etc/systemd/system/futu-opend.service << 'EOL'
[Unit]
Description=Futu OpenD
After=network.target

[Service]
Type=simple
ExecStart=/opt/futu/OpenD/OpenD
WorkingDirectory=/opt/futu/OpenD
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOL

# 5. 提示配置
echo "[5/5] 配置完成!"
echo ""
echo "=========================================="
echo "下一步："
echo "1. 编辑配置文件:"
echo "   vi /opt/futu/OpenD/OpenD.xml"
echo ""
echo "2. 启动服务:"
echo "   systemctl start futu-opend"
echo ""
echo "3. 查看日志:"
echo "   journalctl -u futu-opend -f"
echo "=========================================="
```

---

## 安全提示

1. **不要泄露密码**
2. **使用专用子账户**
3. **设置交易限额**
4. **定期检查日志**

---

## 常见问题

### Q: OpenD启动失败？
A: 检查日志文件，可能是密码错误或网络问题

### Q: 无法连接？
A: 检查防火墙是否开放11111端口

### Q: 需要一直运行吗？
A: 是的，策略需要OpenD在线才能交易

---

## 现在开始

**告诉我你的服务器系统**：
- Ubuntu/Debian?
- CentOS?
- 其他?

**或者我直接帮你生成部署脚本？**

你只需要：
1. 登录服务器
2. 运行我的脚本
3. 输入富途账号

然后就完成部署了！🦞

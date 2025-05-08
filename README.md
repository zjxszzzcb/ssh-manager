实现一个使用cli管理ssh的界面。

* 进入管理界面 python manage-ssh.py

## 管理界面

显示一个界面，读取ssh config文件，左侧显示可以连接的所有客户端名称连接状态显示在管理界面上[alive]/[missing](绿色/红色)，右侧显示该客户端的详细信息(基于ssh config)，上下选择，回车连接ssh终端。

## 终端界面

终端内支持特殊命令，以:开头
1. :back 返回管理界面，继续维持连接
2. :exit 返回管理界面并关闭连接
3. :L/:localforward {localport}:{target_host}:{target_port}


实现一个使用cli管理ssh的界面。

# SSH Manager CLI

一个基于命令行的SSH连接管理工具，用于快速查看、管理和连接SSH配置。

## 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/ssh-manager.git
cd ssh-manager

# 安装依赖
pip install -r requirements.txt
```

## 功能特点

- 读取并显示SSH配置文件中的所有连接
- 实时监控连接状态（在线/离线）
- 快速搜索和过滤连接
- 编辑SSH配置
- 内置终端支持，无需离开界面即可连接SSH
- 便捷的端口转发功能

## 使用方法

启动管理界面：
```bash
python manage-ssh.py
```

## 管理界面设计

```
+--------------------------------------+-------------------------------------+
|                                      |                                     |
|                                      |                                     |
| server1 [alive]                      |  Host: server1.example.com          |
| server2 [missing]                    |  User: user                         |
| dev-machine [alive]                  |  Port: 22                           |
| database [alive]                     |  ...                                |
| backup-server [missing]              |                                     |
|                                      |                                     |
+--------------------------------------+-------------------------------------+
|             Press `Enter` to Connect | `Esc` to Exit                       |
+----------------------------------------------------------------------------+
```

管理界面会显示：
- 左侧：连接列表，上下键选择，显示连接状态（绿色/红色表示在线/离线）
- 右侧：所选连接的详细配置信息
- 底部：提示

### 键盘快捷键

管理界面：
- `↑/↓` - 导航连接列表
- `Enter` - 连接到所选SSH主机
- `Ctrl+E` - 编辑当前选中的SSH配置
- `Ctrl+D` - 删除当前SSH配置(需要确认)
- `Ctrl+N` - 创建新SSH配置
- `Esc` - 退出程序

## 终端界面

连接到SSH主机后，将进入终端模式。终端内支持特殊命令，以冒号开头：

1. `:back` - 返回管理界面，继续维持连接
2. `:exit` - 返回管理界面并关闭连接
3. `:L` 或 `:localforward {localport}:{target_host}:{target_port}` - 设置本地端口转发
4. `:R` 或 `:remoteforward {remoteport}:{target_host}:{target_port}` - 设置远程端口转发
5. `:help` - 显示可用命令列表

终端右侧显示当前连接主机信息(同管理界面)
# Docker 部署

## 快速开始

```bash
# 克隆项目
git clone https://github.com/cnitlrt/AutoTeam.git
cd AutoTeam

# 创建数据目录
mkdir -p data

# 方式一：预先配置（推荐）
cp .env.example data/.env
# 编辑 data/.env 填入实际配置

# 方式二：Web 页面配置
# 直接启动，打开浏览器填写配置

# 启动
docker compose up -d

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

## 数据持久化

所有数据存储在 `data/` 目录下，通过 volume 挂载到容器：

| 文件/目录 | 说明 |
|-----------|------|
| `data/.env` | 配置文件 |
| `data/accounts.json` | 账号数据 |
| `data/state.json` | 管理员登录态 |
| `data/auths/` | Codex 认证文件 |
| `data/screenshots/` | 调试截图 |

重建容器不会丢失数据。

## 手动构建

```bash
docker build -t autoteam .
docker run -d -p 8787:8787 -v $(pwd)/data:/app/data autoteam
```

## 配置方式

### 方式一：预先编辑 .env

启动前编辑 `data/.env`，容器启动后直接可用。

### 方式二：Web 页面配置

不预先配置直接启动，打开 `http://host:8787`，会显示配置向导页面，在浏览器中填写所有配置项。保存后自动验证连通性。

## 常见问题

**Q: 容器一直重启？**

查看日志 `docker compose logs`，可能是配置缺失或连通性验证失败。

**Q: data 目录没有权限？**

容器以 root 运行，entrypoint 会自动 `chmod -R 777 /app/data`，宿主机用户可读写。

**Q: 重建后配置丢失？**

确保使用了 `volumes: - ./data:/app/data` 挂载，配置存在 `data/` 目录不会丢。
